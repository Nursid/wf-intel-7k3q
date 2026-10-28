"""Cutoff-aware forecast selection and forecast/actual interval matching.

Three timestamps are kept distinct throughout:
- decision cutoff  (cutoff_utc): when the procurement decision is made
- publish time     (publish_time_utc): when a forecast became available
- delivery start   (start_time_utc): the delivery interval being forecast

Eligibility: a forecast is usable for a delivery hour only if it was published
  (a) at or before the decision cutoff (publish <= cutoff), and
  (b) at or before the start of that delivery hour (publish <= start).
Rule (b) matters for same-day cutoffs: WINDFOR runs also contain hours that have already started,
and those values are observations rather than forecasts. Nothing ineligible is ever used as a fallback.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

LONDON = ZoneInfo("Europe/London")

# WINDFOR forecasts are hourly (verified in docs/elexon-api-findings.md), so the analysis grid is hourly.
ANALYSIS_FREQ = pd.Timedelta(timedelta(hours=1))
ACTUAL_FREQ = pd.Timedelta(timedelta(minutes=30))

STATUS_MATCHED = "MATCHED"
STATUS_MISSING_FORECAST = "MISSING_FORECAST"
STATUS_MISSING_ACTUAL = "MISSING_ACTUAL"
STATUS_MISSING_BOTH = "MISSING_BOTH"

INELIGIBLE_AFTER_CUTOFF = "AFTER_CUTOFF"
INELIGIBLE_AFTER_DELIVERY_START = "AFTER_DELIVERY_START"


@dataclass(frozen=True)
class CutoffPolicy:
    """Decide `day_offset` days before the delivery day at `local_time` (Europe/London).

    day_offset=1 is the day-ahead case: decide on day D for delivery on D+1.
    """

    day_offset: int = 1
    local_time: time = time(9, 0)

    def __post_init__(self) -> None:
        if self.day_offset < 0:
            raise ValueError("day_offset must be >= 0")

    def cutoff_for(self, delivery_start_utc: datetime) -> datetime:
        if delivery_start_utc.tzinfo is None:
            raise ValueError("delivery_start_utc must be timezone-aware")
        delivery_local_date = delivery_start_utc.astimezone(LONDON).date()
        decision_date = delivery_local_date - timedelta(days=self.day_offset)
        # zoneinfo resolves ambiguous wall times (autumn change) to the first occurrence (fold=0), and
        # non-existent ones (spring gap) using the pre-transition offset. Both are deterministic.
        cutoff_local = datetime.combine(decision_date, self.local_time, tzinfo=LONDON)
        return cutoff_local.astimezone(timezone.utc)

    def delivery_dates(self, decision_start: date, decision_end: date) -> tuple[date, date]:
        """Delivery days covered by decisions taken on decision_start..decision_end."""
        shift = timedelta(days=self.day_offset)
        return decision_start + shift, decision_end + shift

    def describe(self) -> str:
        return f"D-{self.day_offset} at {self.local_time.strftime('%H:%M')} Europe/London"


def local_day_bounds_utc(start_date: date, end_date: date) -> tuple[pd.Timestamp, pd.Timestamp]:
    """UTC [start, end) covering Europe/London calendar days start_date..end_date inclusive."""
    start = datetime.combine(start_date, time(0), tzinfo=LONDON).astimezone(timezone.utc)
    end = datetime.combine(end_date + timedelta(days=1), time(0), tzinfo=LONDON).astimezone(timezone.utc)
    return pd.Timestamp(start), pd.Timestamp(end)


def build_interval_grid(start_date: date, end_date: date, freq: pd.Timedelta = ANALYSIS_FREQ) -> pd.DatetimeIndex:
    """Every expected delivery interval start (UTC) within the Europe/London date range.

    Built in UTC, so DST days naturally contain 23 or 25 hourly intervals (46/50 half-hours).
    """
    if end_date < start_date:
        raise ValueError("end_date must be >= start_date")
    start, end = local_day_bounds_utc(start_date, end_date)
    return pd.date_range(start, end, freq=freq, inclusive="left", name="start_time_utc")


def _eligible_mask(publish: pd.Series, cutoff, start) -> pd.Series:
    return (publish <= cutoff) & (publish <= start)


def select_forecasts(forecasts: pd.DataFrame, targets: pd.DatetimeIndex, policy: CutoffPolicy) -> pd.DataFrame:
    """For each target interval pick the latest eligible forecast (see module docstring).

    Returns one row per target with columns:
    start_time_utc, cutoff_utc, forecast_mw, publish_time_utc, eligible_versions, total_versions,
    lead_time_minutes (cutoff - publish), horizon_minutes (start - publish).
    Targets without an eligible forecast get NaN/NaT.
    """
    out = pd.DataFrame({"start_time_utc": targets})
    out["cutoff_utc"] = pd.to_datetime([policy.cutoff_for(t.to_pydatetime()) for t in targets], utc=True)

    f = forecasts[forecasts["start_time_utc"].isin(targets)]
    f = f.merge(out[["start_time_utc", "cutoff_utc"]], on="start_time_utc", how="inner")
    total = f.groupby("start_time_utc").size().rename("total_versions")

    eligible = f[_eligible_mask(f["publish_time_utc"], f["cutoff_utc"], f["start_time_utc"])]
    n_eligible = eligible.groupby("start_time_utc").size().rename("eligible_versions")
    latest = (
        eligible.sort_values(["start_time_utc", "publish_time_utc"])
        .drop_duplicates("start_time_utc", keep="last")
        .set_index("start_time_utc")[["forecast_mw", "publish_time_utc"]]
    )

    out = out.set_index("start_time_utc").join(latest).join(n_eligible).join(total).reset_index()
    out["eligible_versions"] = out["eligible_versions"].fillna(0).astype(int)
    out["total_versions"] = out["total_versions"].fillna(0).astype(int)
    out["lead_time_minutes"] = (out["cutoff_utc"] - out["publish_time_utc"]).dt.total_seconds() / 60
    out["horizon_minutes"] = (out["start_time_utc"] - out["publish_time_utc"]).dt.total_seconds() / 60
    return out


def match_intervals(selected: pd.DataFrame, actuals: pd.DataFrame) -> pd.DataFrame:
    """Join selected forecasts to actuals on the exact delivery start time and assign a status."""
    a = actuals[["start_time_utc", "actual_mw"]]
    df = selected.merge(a, on="start_time_utc", how="left")
    has_f = df["forecast_mw"].notna()
    has_a = df["actual_mw"].notna()
    df["status"] = np.select(
        [has_f & has_a, ~has_f & has_a, has_f & ~has_a],
        [STATUS_MATCHED, STATUS_MISSING_FORECAST, STATUS_MISSING_ACTUAL],
        default=STATUS_MISSING_BOTH,
    )
    df["error_mw"] = np.where(has_f & has_a, df["forecast_mw"] - df["actual_mw"], np.nan)
    df["abs_error_mw"] = df["error_mw"].abs()
    return df


def forecast_versions(forecasts: pd.DataFrame, start_time_utc: pd.Timestamp, policy: CutoffPolicy) -> pd.DataFrame:
    """All published versions for one delivery interval, flagged eligible/selected with a reason if not."""
    cutoff = pd.Timestamp(policy.cutoff_for(start_time_utc.to_pydatetime()))
    v = forecasts[forecasts["start_time_utc"] == start_time_utc].sort_values("publish_time_utc").copy()
    v["eligible"] = _eligible_mask(v["publish_time_utc"], cutoff, start_time_utc)
    v["ineligible_reason"] = [
        None if ok else (INELIGIBLE_AFTER_CUTOFF if p > cutoff else INELIGIBLE_AFTER_DELIVERY_START)
        for ok, p in zip(v["eligible"], v["publish_time_utc"])
    ]
    v["selected"] = False
    if v["eligible"].any():
        v.loc[v[v["eligible"]].index[-1], "selected"] = True
    v["cutoff_utc"] = cutoff
    return v.reset_index(drop=True)
