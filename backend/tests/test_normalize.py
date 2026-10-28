import pandas as pd

from app.services.normalize import normalize_actuals, normalize_forecasts


def a(start="2026-01-01T00:00:00Z", gen=100, fuel="WIND", pub="2026-01-01T00:30:00Z"):
    return {"startTime": start, "publishTime": pub, "fuelType": fuel, "generation": gen}


def test_actuals_filters_non_wind_and_counts_invalid():
    raw = [
        a(),
        a(start="2026-01-01T00:30:00Z", fuel="CCGT"),
        a(start="2026-01-01T01:00:00Z", gen=None),
        a(start="2026-01-01T01:30:00Z", gen="abc"),
        a(start="2026-01-01T02:00:00Z", gen=float("nan")),
        a(start="2026-01-01T02:30:00Z", gen=True),
        a(start="2026-01-01T03:00:00"),  # naive timestamp
        {"startTime": "2026-01-01T03:30:00Z", "fuelType": "WIND"},  # missing generation
        "not-a-dict",
    ]
    df, rep = normalize_actuals([r for r in raw if isinstance(r, dict)])
    assert len(df) == 1 and df.actual_mw.iloc[0] == 100.0
    assert rep.non_wind == 1 and rep.invalid == 6 and rep.accepted == 1


def test_actuals_revision_keeps_latest_publication():
    df, rep = normalize_actuals([a(gen=100, pub="2026-01-01T00:30:00Z"), a(gen=120, pub="2026-01-01T02:00:00Z")])
    assert df.actual_mw.tolist() == [120.0] and rep.duplicates == 1


def test_timestamps_converted_to_utc():
    df, _ = normalize_actuals([a(start="2026-06-01T01:00:00+01:00")])
    assert df.start_time_utc.iloc[0] == pd.Timestamp("2026-06-01T00:00:00Z")
    assert str(df.start_time_utc.dt.tz) == "UTC"


def test_forecasts_dedupe_exact_duplicates_only():
    raw = [
        {"startTime": "2026-01-01T00:00:00Z", "publishTime": "2025-12-31T09:30:00Z", "generation": 5},
        {"startTime": "2026-01-01T00:00:00Z", "publishTime": "2025-12-31T09:30:00Z", "generation": 5},
        {"startTime": "2026-01-01T00:00:00Z", "publishTime": "2025-12-31T11:30:00Z", "generation": 6},
        {"startTime": "2026-01-01T00:00:00Z", "publishTime": None, "generation": 7},
    ]
    df, rep = normalize_forecasts(raw)
    assert len(df) == 2 and rep.duplicates == 1 and rep.invalid == 1


def test_empty_input_gives_typed_empty_frames():
    df, rep = normalize_forecasts([])
    assert df.empty and list(df.columns) == ["start_time_utc", "publish_time_utc", "forecast_mw"]
    assert rep.received == 0
