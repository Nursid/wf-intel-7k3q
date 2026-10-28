from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from app.services.forecast_selector import (
    ACTUAL_FREQ,
    CutoffPolicy,
    build_interval_grid,
    forecast_versions,
    match_intervals,
    select_forecasts,
)
from tests.conftest import actuals_df, forecasts_df, ts

D1_0900 = CutoffPolicy(mode="relative", day_offset=1, local_time=time(9, 0))
T = "2026-01-02T12:00Z"  # delivery; cutoff under D1_0900 = 2026-01-01T09:00Z (GMT)


def grid(*starts: str) -> pd.DatetimeIndex:
    return pd.DatetimeIndex([ts(s) for s in starts], name="start_time_utc")


# 1. latest eligible forecast before cutoff
def test_selects_latest_forecast_published_before_cutoff():
    f = forecasts_df([
        (T, "2025-12-31T09:30Z", 100),
        (T, "2026-01-01T07:30Z", 200),
        (T, "2026-01-01T04:30Z", 150),
    ])
    out = select_forecasts(f, grid(T), D1_0900).iloc[0]
    assert out.forecast_mw == 200
    assert out.publish_time_utc == ts("2026-01-01T07:30Z")
    assert out.cutoff_utc == ts("2026-01-01T09:00Z")
    assert out.eligible_versions == 3 and out.total_versions == 3
    assert out.lead_time_minutes == 90
    assert out.horizon_minutes == pytest.approx(28.5 * 60)


# 2. forecasts published after cutoff are excluded (incl. 1 second after); equal-to-cutoff is eligible
def test_excludes_forecasts_published_after_cutoff():
    f = forecasts_df([
        (T, "2026-01-01T07:30Z", 200),
        (T, "2026-01-01T09:00:01Z", 999),
        (T, "2026-01-01T22:30Z", 888),
    ])
    out = select_forecasts(f, grid(T), D1_0900).iloc[0]
    assert out.forecast_mw == 200
    assert out.eligible_versions == 1 and out.total_versions == 3


def test_forecast_published_exactly_at_cutoff_is_eligible():
    f = forecasts_df([(T, "2026-01-01T07:30Z", 200), (T, "2026-01-01T09:00Z", 210)])
    out = select_forecasts(f, grid(T), D1_0900).iloc[0]
    assert out.forecast_mw == 210 and out.lead_time_minutes == 0


def test_no_eligible_forecast_never_falls_back_to_later_one():
    f = forecasts_df([(T, "2026-01-01T10:00Z", 999)])
    out = select_forecasts(f, grid(T), D1_0900).iloc[0]
    assert np.isnan(out.forecast_mw) and pd.isna(out.publish_time_utc)
    assert out.eligible_versions == 0 and out.total_versions == 1


# 3. multiple forecasts / multiple intervals are selected independently
def test_multiple_intervals_each_use_their_own_cutoff():
    t1, t2 = "2026-01-02T23:00Z", "2026-01-03T00:00Z"  # different delivery days -> different cutoffs
    f = forecasts_df([
        (t1, "2026-01-01T08:00Z", 10), (t1, "2026-01-01T12:00Z", 11),
        (t2, "2026-01-01T08:00Z", 20), (t2, "2026-01-01T12:00Z", 21), (t2, "2026-01-02T09:30Z", 22),
    ])
    out = select_forecasts(f, grid(t1, t2), D1_0900).set_index("start_time_utc")
    assert out.loc[ts(t1), "forecast_mw"] == 10   # cutoff 1 Jan 09:00
    assert out.loc[ts(t2), "forecast_mw"] == 21   # cutoff 2 Jan 09:00
    assert out.loc[ts(t2), "eligible_versions"] == 2


def test_absolute_policy_applies_one_decision_time():
    p = CutoffPolicy(mode="absolute", decision_at=datetime(2026, 1, 1, 12, tzinfo=timezone.utc))
    f = forecasts_df([(T, "2026-01-01T11:30Z", 1), (T, "2026-01-01T12:30Z", 2)])
    assert select_forecasts(f, grid(T), p).iloc[0].forecast_mw == 1


def test_absolute_policy_requires_aware_decision_time():
    with pytest.raises(ValueError):
        CutoffPolicy(mode="absolute", decision_at=datetime(2026, 1, 1, 12))
    with pytest.raises(ValueError):
        CutoffPolicy(mode="absolute")


# 4 & 5. missing records and matching on delivery interval
def test_match_assigns_status_and_errors_only_for_matched():
    sel = select_forecasts(
        forecasts_df([("2026-01-02T00:00Z", "2026-01-01T08:00Z", 110), ("2026-01-02T02:00Z", "2026-01-01T08:00Z", 90)]),
        grid("2026-01-02T00:00Z", "2026-01-02T01:00Z", "2026-01-02T02:00Z", "2026-01-02T03:00Z"),
        D1_0900,
    )
    a = actuals_df([("2026-01-02T00:00Z", 100), ("2026-01-02T00:30Z", 5000), ("2026-01-02T01:00Z", 100)])
    m = match_intervals(sel, a).set_index("start_time_utc")
    assert list(m["status"]) == ["MATCHED", "MISSING_FORECAST", "MISSING_ACTUAL", "MISSING_BOTH"]
    assert m.loc[ts("2026-01-02T00:00Z"), "error_mw"] == 10
    assert m.loc[ts("2026-01-02T00:00Z"), "actual_mw"] == 100  # exact startTime, not the 00:30 slot
    assert m["error_mw"].isna().sum() == 3


# 9. UTC vs Europe/London handling
@pytest.mark.parametrize(
    "delivery, expected_cutoff",
    [
        ("2026-01-01T23:30Z", "2025-12-31T09:00Z"),  # GMT: local == UTC
        ("2026-03-29T00:30Z", "2026-03-28T09:00Z"),  # BST change day; delivery local date 29 Mar (GMT 00:30)
        ("2026-03-30T12:00Z", "2026-03-29T08:00Z"),  # cutoff 09:00 BST on 29 Mar = 08:00Z
        ("2026-06-01T23:30Z", "2026-06-01T08:00Z"),  # local 2 Jun 00:30 BST -> D-1 = 1 Jun 09:00 BST
        ("2026-10-25T12:00Z", "2026-10-24T08:00Z"),  # GMT returns 25 Oct; cutoff on 24 Oct still BST
    ],
)
def test_relative_cutoff_uses_europe_london_calendar(delivery, expected_cutoff):
    assert D1_0900.cutoff_for(ts(delivery).to_pydatetime()) == ts(expected_cutoff).to_pydatetime()


def test_cutoff_requires_aware_delivery_time():
    with pytest.raises(ValueError):
        D1_0900.cutoff_for(datetime(2026, 1, 2, 12))


@pytest.mark.parametrize(
    "day, freq, n",
    [
        (date(2026, 1, 15), None, 24),
        (date(2026, 3, 29), None, 23),
        (date(2026, 10, 25), None, 25),
        (date(2026, 3, 29), ACTUAL_FREQ, 46),
        (date(2026, 1, 15), ACTUAL_FREQ, 48),
    ],
)
def test_interval_grid_respects_dst(day, freq, n):
    g = build_interval_grid(day, day) if freq is None else build_interval_grid(day, day, freq)
    assert len(g) == n
    assert str(g.tz) == "UTC"
    assert g[0].tz_convert(ZoneInfo("Europe/London")).hour == 0


def test_grid_rejects_inverted_range():
    with pytest.raises(ValueError):
        build_interval_grid(date(2026, 1, 2), date(2026, 1, 1))


def test_forecast_versions_flags_eligibility_and_selection():
    f = forecasts_df([
        (T, "2026-01-01T07:30Z", 200), (T, "2025-12-31T09:30Z", 100), (T, "2026-01-01T09:30Z", 300),
        ("2026-01-02T13:00Z", "2026-01-01T07:30Z", 1),
    ])
    v = forecast_versions(f, ts(T), D1_0900)
    assert list(v["forecast_mw"]) == [100, 200, 300]
    assert list(v["eligible"]) == [True, True, False]
    assert list(v["selected"]) == [False, True, False]


@pytest.mark.parametrize("offset, hhmm", [(0, "07:00"), (1, "09:00"), (1, "16:30"), (2, "09:00")])
def test_invariant_on_real_fixture_never_selects_post_cutoff(offset, hhmm):
    """Scan every delivery hour of the bundled (real Elexon) demo fixture."""
    from app.services.data_repository import FIXTURE_PATH, _payload_to_dataset
    import json

    ds = _payload_to_dataset(json.loads(FIXTURE_PATH.read_text(encoding="utf-8")))
    policy = CutoffPolicy(day_offset=offset, local_time=time.fromisoformat(hhmm))
    grid_ = build_interval_grid(date(2026, 1, 1), date(2026, 1, 3))
    sel = select_forecasts(ds.forecasts, grid_, policy)
    picked = sel.dropna(subset=["publish_time_utc"])
    assert (picked["publish_time_utc"] <= picked["cutoff_utc"]).all()
    # and it is the latest eligible version
    for row in picked.itertuples():
        v = ds.forecasts[(ds.forecasts.start_time_utc == row.start_time_utc) & (ds.forecasts.publish_time_utc <= row.cutoff_utc)]
        assert row.publish_time_utc == v.publish_time_utc.max()
