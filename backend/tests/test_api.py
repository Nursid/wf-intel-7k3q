import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.data_repository import DataRepository
from app.services.elexon_client import ElexonUnavailableError
from tests.conftest import FakeClient

# Day-ahead decisions on 1-2 Jan -> deliveries on 2-3 Jan (the synthetic data window).
DECISIONS_1_2 = {"decision_start_date": "2026-01-01", "decision_end_date": "2026-01-02"}


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok" and r.json()["dataset_loaded"] is False


def test_meta(client):
    body = client.get("/api/meta").json()
    assert body["decision_start_date"] == "2026-01-01" and body["decision_end_date"] == "2026-01-31"
    assert body["max_day_offset"] == 3
    assert body["default_cutoff"]["description"] == "D-1 at 09:00 Europe/London"
    assert body["analysis_resolution_minutes"] == 60
    assert body["data_source"]["mode"] == "LIVE"
    assert body["data_source"]["fetched_at_utc"].endswith("Z")
    assert body["assumptions"]


def test_period_is_defined_by_decision_dates(client):
    """January decisions with a day-ahead rule cover deliveries 2 Jan - 1 Feb (not 1-31 Jan)."""
    p = client.get("/api/analysis/overview").json()["period"]
    assert (p["decision_start_date"], p["decision_end_date"]) == ("2026-01-01", "2026-01-31")
    assert (p["delivery_start_date"], p["delivery_end_date"]) == ("2026-01-02", "2026-02-01")
    assert p["start_utc"] == "2026-01-02T00:00:00Z" and p["end_utc"] == "2026-02-02T00:00:00Z"

    same_day = client.get("/api/analysis/overview", params={"cutoff_day_offset": 0}).json()["period"]
    assert (same_day["delivery_start_date"], same_day["delivery_end_date"]) == ("2026-01-01", "2026-01-31")


def test_overview_metrics_follow_cutoff(client):
    m = client.get("/api/analysis/overview", params=DECISIONS_1_2).json()["metrics"]
    # default cutoff D-1 09:00 picks the D-1 08:30 version (+50 MW); the 10:00 version (+10) is post-cutoff
    assert m["expected_count"] == 48
    assert m["matched_count"] == 46
    assert m["missing_forecast_count"] == 1 and m["missing_actual_count"] == 1
    assert m["mae_mw"] == pytest.approx(50) and m["mbe_mw"] == pytest.approx(50) and m["rmse_mw"] == pytest.approx(50)
    assert m["coverage_pct"] == pytest.approx(46 / 48 * 100)


def test_overview_later_cutoff_uses_later_forecast(client):
    m = client.get("/api/analysis/overview", params={**DECISIONS_1_2, "cutoff_time": "10:00"}).json()["metrics"]
    assert m["mae_mw"] == pytest.approx(10)


def test_same_day_cutoff_never_uses_versions_published_after_the_hour_began(client):
    # D-0 at 12:00: for 00:00-11:00 the "+1 MW nowcast" (published at hh:30) is before the cutoff but after
    # the hour started, so it must be skipped in favour of the D-1 10:00 version (+10 MW).
    params = {"decision_start_date": "2026-01-02", "decision_end_date": "2026-01-03", "cutoff_day_offset": 0, "cutoff_time": "12:00"}
    m = client.get("/api/analysis/overview", params=params).json()["metrics"]
    assert m["mbe_mw"] == pytest.approx(10) and m["mae_mw"] == pytest.approx(10)
    items = client.get("/api/analysis/intervals", params={**params, "page_size": 500}).json()["items"]
    assert all(i["horizon_minutes"] is None or i["horizon_minutes"] >= 0 for i in items)


def test_error_distribution(client):
    d = client.get("/api/analysis/overview", params=DECISIONS_1_2).json()["error_distribution"]
    assert d["n"] == 46
    assert d["percentiles_mw"]["p10"] == pytest.approx(50) and d["percentiles_mw"]["p90"] == pytest.approx(50)
    r80 = next(r for r in d["actual_ranges"] if r["coverage_pct"] == 80)
    assert r80["low_mw"] == pytest.approx(-50) and r80["high_mw"] == pytest.approx(-50)
    assert d["within"][0] == {"threshold_mw": 500, "pct": 100.0}
    assert d["over_forecast_pct"] == 100.0
    assert sum(b["count"] for b in d["histogram"]) == 46


def test_error_distribution_null_when_nothing_matched(client):
    body = client.get("/api/analysis/overview", params={**DECISIONS_1_2, "cutoff_day_offset": 3}).json()
    assert body["metrics"]["matched_count"] == 0 and body["error_distribution"] is None


def test_timeseries(client):
    body = client.get("/api/analysis/timeseries", params={"decision_start_date": "2026-01-02", "decision_end_date": "2026-01-02"}).json()
    assert body["period"]["delivery_start_date"] == "2026-01-03"
    assert len(body["intervals"]) == 24
    assert len(body["actuals_half_hourly"]) == 47  # one half-hour missing in the source
    missing = [p for p in body["intervals"] if p["status"] == "MISSING_FORECAST"]
    assert missing[0]["forecast_mw"] is None and missing[0]["error_mw"] is None and missing[0]["range_low_mw"] is None
    first = body["intervals"][0]
    assert first["publish_time_utc"] == "2026-01-02T08:30:00Z"
    # every error is +50, so the 80 % range for actual collapses to forecast - 50 = actual
    assert first["range_low_mw"] == pytest.approx(first["actual_mw"]) and first["range_high_mw"] == pytest.approx(first["actual_mw"])


def test_intervals_pagination_and_sorting(client):
    r = client.get("/api/analysis/intervals", params={**DECISIONS_1_2, "page": 2, "page_size": 20}).json()
    assert r["total"] == 48 and r["total_pages"] == 3 and len(r["items"]) == 20
    assert r["items"][0]["start_time_utc"] == "2026-01-02T20:00:00Z"

    r = client.get("/api/analysis/intervals", params={**DECISIONS_1_2, "sort_by": "actual_mw", "sort_dir": "desc"}).json()
    vals = [i["actual_mw"] for i in r["items"] if i["actual_mw"] is not None]
    assert vals == sorted(vals, reverse=True)

    r = client.get("/api/analysis/intervals", params={**DECISIONS_1_2, "sort_by": "error_mw", "page_size": 500}).json()
    assert r["items"][-1]["error_mw"] is None  # missing values sort last


def test_forecast_history_never_selects_post_cutoff(client):
    r = client.get("/api/analysis/forecast-history", params={"start_time": "2026-01-03T12:00:00Z"}).json()
    assert r["cutoff_utc"] == "2026-01-02T09:00:00Z"
    assert r["total_versions"] == 4 and r["eligible_versions"] == 2
    assert r["selected"]["publish_time_utc"] == "2026-01-02T08:30:00Z"
    assert r["selected"]["minutes_before_cutoff"] == 30
    late = [v for v in r["versions"] if v["publish_time_utc"] == "2026-01-02T10:00:00Z"][0]
    assert late["eligible"] is False and late["selected"] is False and late["minutes_before_cutoff"] == -60
    assert late["ineligible_reason"] == "AFTER_CUTOFF"
    assert r["actual_mw"] == 1072.0


def test_forecast_history_flags_versions_after_delivery_start(client):
    params = {"start_time": "2026-01-03T03:00:00Z", "cutoff_day_offset": 0, "cutoff_time": "12:00"}
    r = client.get("/api/analysis/forecast-history", params=params).json()
    nowcast = [v for v in r["versions"] if v["publish_time_utc"] == "2026-01-03T03:30:00Z"][0]
    assert nowcast["eligible"] is False and nowcast["ineligible_reason"] == "AFTER_DELIVERY_START"
    assert r["selected"]["publish_time_utc"] == "2026-01-02T10:00:00Z"


@pytest.mark.parametrize(
    "path, params, fragment",
    [
        ("/api/analysis/overview", {"decision_start_date": "2025-12-31"}, "between"),
        ("/api/analysis/overview", {"decision_start_date": "2026-01-10", "decision_end_date": "2026-01-05"}, "on or after"),
        ("/api/analysis/overview", {"decision_end_date": "2026-02-01"}, "between"),
        ("/api/analysis/overview", {"cutoff_time": "9am"}, "HH:MM"),
        ("/api/analysis/overview", {"cutoff_day_offset": 4}, "between 0 and 3"),
        ("/api/analysis/overview", {"decision_start_date": "not-a-date"}, "decision_start_date"),
        ("/api/analysis/intervals", {"sort_by": "secret"}, "sort_by"),
        ("/api/analysis/intervals", {"page": 0}, "page"),
        ("/api/analysis/forecast-history", {"start_time": "2026-01-02T12:30:00Z"}, "hourly"),
        # 1 Jan delivery is decided on 31 Dec under D-1: outside January decisions
        ("/api/analysis/forecast-history", {"start_time": "2026-01-01T12:00:00Z"}, "outside"),
        ("/api/analysis/forecast-history", {"start_time": "2026-02-03T12:00:00Z"}, "outside"),
        ("/api/analysis/forecast-history", {}, "start_time"),
    ],
)
def test_validation_errors(client, path, params, fragment):
    r = client.get(path, params=params)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "INVALID_REQUEST"
    assert fragment in r.json()["error"]["message"]


def test_source_unavailable_returns_503(settings):
    repo = DataRepository(settings, client_factory=lambda: FakeClient(fail=ElexonUnavailableError("down")))
    r = TestClient(create_app(settings, repo)).get("/api/analysis/overview")
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "SOURCE_UNAVAILABLE"


def test_stale_cache_is_disclosed(settings):
    DataRepository(settings, client_factory=FakeClient).get()
    expired = settings.model_copy(update={"cache_ttl_hours": 1e-9})
    repo = DataRepository(expired, client_factory=lambda: FakeClient(fail=ElexonUnavailableError("down")))
    ds = TestClient(create_app(expired, repo)).get("/api/meta").json()["data_source"]
    assert ds["stale"] is True and ds["errors"] == ["down"]


def test_fixture_mode_is_labelled_demo(settings):
    s = settings.model_copy(update={"data_mode": "fixture"})
    body = TestClient(create_app(s, DataRepository(s))).get("/api/meta").json()
    assert body["data_source"]["mode"] == "DEMO FIXTURE"


def test_admin_refresh_requires_token(client, fake_client):
    assert client.post("/api/admin/refresh").status_code == 403
    r = client.post("/api/admin/refresh", headers={"X-Admin-Token": "secret"})
    assert r.status_code == 200 and fake_client.calls == 1


def test_cors_allows_configured_origin_only(client):
    ok = client.get("/health", headers={"Origin": "http://localhost:5173"})
    bad = client.get("/health", headers={"Origin": "https://evil.example"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "access-control-allow-origin" not in bad.headers
