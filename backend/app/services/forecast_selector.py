"""Cutoff-aware forecast selection and forecast/actual interval matching.

Three timestamps are kept distinct throughout:
- decision cutoff  (cutoff_utc): when the procurement decision is made
- publish time     (publish_time_utc): when a forecast became available
- delivery start   (start_time_utc): the delivery interval being forecast

Boundary rule: a forecast published exactly at the cutoff counts as eligible (publish <= cutoff).
A forecast published after the cutoff is never selected, and there is no fallback to later forecasts.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal
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


@dataclass(frozen=True)
class CutoffPolicy:
    """`relative`: cutoff = (delivery's Europe/London date - day_offset) at local_time, Europe/London.
    `absolute`: one fixed decision timestamp for every interval.
    """

    mode: Literal["relative", "absolute"] = "relative"
    day_offset: int = 1
    local_time: time = time(9, 0)
    decision_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.mode == "absolute":
            if self.decision_at is None:
                raise ValueError("absolute cutoff requires decision_at")
            if self.decision_at.tzinfo is None:
                raise ValueError("decision_at must be timezone-aware")
        elif self.day_offset < 0:
            raise ValueError("day_offset must be >= 0")

    def cutoff_for(self, delivery_start_utc: datetime) -> datetime:
        if delivery_start_utc.tzinfo is None:
            raise ValueError("delivery_start_utc must be timezone-aware")
        if self.mode == "absolute":
            return self.decision_at.astimezone(timezone.utc)  # type: ignore[union-attr]
        delivery_local_date = delivery_start_utc.astimezone(LONDON).date()
        decision_date = delivery_local_date - timedelta(days=self.day_offset)
        # zoneinfo resolves ambiguous wall times (autumn change) to the first occurrence (fold=0), and
        # non-existent ones (spring gap) using the pre-transition offset. Both are deterministic.
        cutoff_local = datetime.combine(decision_date, self.local_time, tzinfo=LONDON)
        return cutoff_local.astimezone(timezone.utc)

    def describe(self) -> str:
        if self.mode == "absolute":
            return f"Fixed decision time {self.decision_at.astimezone(timezone.utc):%Y-%m-%d %H:%M} UTC"  # type: ignore[union-attr]
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


def select_forecasts(forecasts: pd.DataFrame, targets: pd.DatetimeIndex, policy: CutoffPolicy) -> pd.DataFrame:
    """For each target interval pick the latest forecast published at or before its cutoff.

    Returns one row per target with columns:
    start_time_utc, cutoff_utc, forecast_mw, publish_time_utc, eligible_versions, total_versions,
    lead_time_minutes (cutoff - publish), horizon_minutes (start - publish).
    Targets without an eligible forecast get NaN/NaT, never a value from after the cutoff.
    """
    out = pd.DataFrame({"start_time_utc": targets})
    out["cutoff_utc"] = pd.to_datetime(
        [policy.cutoff_for(t.to_pydatetime()) for t in targets], utc=True
    ) if len(targets) else pd.Series([], dtype="datetime64[ns, UTC]")

    f = forecasts[forecasts["start_time_utc"].isin(targets)]
    f = f.merge(out[["start_time_utc", "cutoff_utc"]], on="start_time_utc", how="inner")
    total = f.groupby("start_time_utc").size().rename("total_versions")

    eligible = f[f["publish_time_utc"] <= f["cutoff_utc"]]
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
    """All published versions for one delivery interval, flagged eligible/selected."""
    cutoff = pd.Timestamp(policy.cutoff_for(start_time_utc.to_pydatetime()))
    v = forecasts[forecasts["start_time_utc"] == start_time_utc].sort_values("publish_time_utc").copy()
    v["eligible"] = v["publish_time_utc"] <= cutoff
    v["selected"] = False
    if v["eligible"].any():
        v.loc[v[v["eligible"]].index[-1], "selected"] = True
    v["cutoff_utc"] = cutoff
    return v.reset_index(drop=True)
