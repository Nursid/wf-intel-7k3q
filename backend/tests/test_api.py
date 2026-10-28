import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.data_repository import DataRepository
from app.services.elexon_client import ElexonUnavailableError
from tests.conftest import FakeClient

DAYS_1_2 = {"start_date": "2026-01-01", "end_date": "2026-01-02"}


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok" and r.json()["dataset_loaded"] is False


def test_meta(client):
    body = client.get("/api/meta").json()
    assert body["available_start_date"] == "2026-01-01"
    assert body["default_cutoff"]["description"] == "D-1 at 09:00 Europe/London"
    assert body["analysis_resolution_minutes"] == 60
    assert body["data_source"]["mode"] == "LIVE"
    assert body["data_source"]["fetched_at_utc"].endswith("Z")
    assert body["assumptions"]


def test_overview_metrics_follow_cutoff(client):
    m = client.get("/api/analysis/overview", params=DAYS_1_2).json()["metrics"]
    # default cutoff D-1 09:00 picks the D-1 08:30 version (+50 MW); the 10:00 version (+10) is post-cutoff
    assert m["expected_count"] == 48
    assert m["matched_count"] == 46
    assert m["missing_forecast_count"] == 1 and m["missing_actual_count"] == 1
    assert m["mae_mw"] == pytest.approx(50) and m["mbe_mw"] == pytest.approx(50) and m["rmse_mw"] == pytest.approx(50)
    assert m["coverage_pct"] == pytest.approx(46 / 48 * 100)


def test_overview_later_cutoff_uses_later_forecast(client):
    m = client.get("/api/analysis/overview", params={**DAYS_1_2, "cutoff_time": "10:00"}).json()["metrics"]
    assert m["mae_mw"] == pytest.approx(10)


def test_overview_absolute_cutoff(client):
    params = {**DAYS_1_2, "cutoff_mode": "absolute", "decision_at": "2025-12-31T08:45:00+00:00"}
    m = client.get("/api/analysis/overview", params=params).json()["metrics"]
    # day 1 hours: D-1 08:30 (+50) eligible; day 2 hours: only the D-2 08:00 version (+100)
    assert m["mbe_mw"] == pytest.approx((24 * 50 + 22 * 100) / 46)


def test_timeseries(client):
    body = client.get("/api/analysis/timeseries", params={"start_date": "2026-01-02", "end_date": "2026-01-02"}).json()
    assert len(body["intervals"]) == 24
    assert len(body["actuals_half_hourly"]) == 47  # one half-hour missing in the source
    missing = [p for p in body["intervals"] if p["status"] == "MISSING_FORECAST"]
    assert missing[0]["forecast_mw"] is None and missing[0]["error_mw"] is None
    assert body["intervals"][0]["publish_time_utc"] == "2026-01-01T08:30:00Z"


def test_intervals_pagination_and_sorting(client):
    r = client.get("/api/analysis/intervals", params={**DAYS_1_2, "page": 2, "page_size": 20}).json()
    assert r["total"] == 48 and r["total_pages"] == 3 and len(r["items"]) == 20
    assert r["items"][0]["start_time_utc"] == "2026-01-01T20:00:00Z"

    r = client.get("/api/analysis/intervals", params={**DAYS_1_2, "sort_by": "actual_mw", "sort_dir": "desc"}).json()
    vals = [i["actual_mw"] for i in r["items"] if i["actual_mw"] is not None]
    assert vals == sorted(vals, reverse=True)

    r = client.get("/api/analysis/intervals", params={**DAYS_1_2, "sort_by": "error_mw", "page_size": 500}).json()
    assert r["items"][-1]["error_mw"] is None  # missing values sort last


def test_forecast_history_never_selects_post_cutoff(client):
    r = client.get("/api/analysis/forecast-history", params={"start_time": "2026-01-02T12:00:00Z"}).json()
    assert r["cutoff_utc"] == "2026-01-01T09:00:00Z"
    assert r["total_versions"] == 3 and r["eligible_versions"] == 2
    assert r["selected"]["publish_time_utc"] == "2026-01-01T08:30:00Z"
    assert r["selected"]["minutes_before_cutoff"] == 30
    late = [v for v in r["versions"] if v["publish_time_utc"] == "2026-01-01T10:00:00Z"][0]
    assert late["eligible"] is False and late["selected"] is False and late["minutes_before_cutoff"] == -60
    assert r["actual_mw"] == 1072.0


@pytest.mark.parametrize(
    "path, params, fragment",
    [
        ("/api/analysis/overview", {"start_date": "2025-12-31"}, "between"),
        ("/api/analysis/overview", {"start_date": "2026-01-10", "end_date": "2026-01-05"}, "on or after"),
        ("/api/analysis/overview", {"end_date": "2026-02-01"}, "between"),
        ("/api/analysis/overview", {"cutoff_mode": "absolute"}, "decision_at is required"),
        ("/api/analysis/overview", {"cutoff_mode": "absolute", "decision_at": "2026-01-01T09:00:00"}, "timezone"),
        ("/api/analysis/overview", {"cutoff_time": "9am"}, "HH:MM"),
        ("/api/analysis/overview", {"cutoff_day_offset": 9}, "between 0 and 7"),
        ("/api/analysis/overview", {"start_date": "not-a-date"}, "start_date"),
        ("/api/analysis/intervals", {"sort_by": "secret"}, "sort_by"),
        ("/api/analysis/intervals", {"page": 0}, "page"),
        ("/api/analysis/forecast-history", {"start_time": "2026-01-02T12:30:00Z"}, "hourly"),
        ("/api/analysis/forecast-history", {"start_time": "2026-02-02T12:00:00Z"}, "outside"),
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
