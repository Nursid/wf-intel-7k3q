from datetime import date, datetime, timezone

import httpx
import pytest
import respx

from app.services.elexon_client import ElexonClient, ElexonResponseError, ElexonUnavailableError

BASE = "https://elexon.test/api"


@pytest.fixture
def sleeps():
    return []


@pytest.fixture
def client(sleeps):
    c = ElexonClient(BASE, max_retries=2, backoff_s=1.0, chunk_days=7, sleep=sleeps.append)
    yield c
    c.close()


@respx.mock
def test_actuals_are_chunked_by_settlement_date(client):
    route = respx.get(f"{BASE}/datasets/FUELHH/stream").mock(return_value=httpx.Response(200, json=[{"x": 1}]))
    rows = client.fetch_wind_actuals(date(2026, 1, 1), date(2026, 1, 20))
    assert len(rows) == 3 and route.call_count == 3
    params = [dict(c.request.url.params) for c in route.calls]
    assert params[0] == {"settlementDateFrom": "2026-01-01", "settlementDateTo": "2026-01-07", "fuelType": "WIND"}
    assert params[2]["settlementDateFrom"] == "2026-01-15" and params[2]["settlementDateTo"] == "2026-01-20"


@respx.mock
def test_forecasts_are_chunked_by_publish_window(client):
    route = respx.get(f"{BASE}/datasets/WINDFOR/stream").mock(return_value=httpx.Response(200, json=[]))
    client.fetch_wind_forecasts(datetime(2025, 12, 24, tzinfo=timezone.utc), datetime(2026, 1, 10, tzinfo=timezone.utc))
    p = [dict(c.request.url.params) for c in route.calls]
    assert len(p) == 3
    assert p[0] == {"publishDateTimeFrom": "2025-12-24T00:00:00Z", "publishDateTimeTo": "2025-12-31T00:00:00Z"}
    assert p[-1]["publishDateTimeTo"] == "2026-01-10T00:00:00Z"


def test_forecast_window_must_be_aware(client):
    with pytest.raises(ValueError):
        client.fetch_wind_forecasts(datetime(2026, 1, 1), datetime(2026, 1, 2))


@respx.mock
@pytest.mark.parametrize("status", [429, 500, 503])
def test_retries_retryable_status_then_succeeds(client, sleeps, status):
    respx.get(f"{BASE}/datasets/WINDFOR/stream").mock(
        side_effect=[httpx.Response(status), httpx.Response(status), httpx.Response(200, json=[{"a": 1}])]
    )
    rows = client.fetch_wind_forecasts(datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 2, tzinfo=timezone.utc))
    assert rows == [{"a": 1}]
    assert sleeps == [1.0, 2.0]  # exponential backoff


@respx.mock
def test_gives_up_after_retries_on_timeout(client):
    route = respx.get(f"{BASE}/datasets/FUELHH/stream").mock(side_effect=httpx.ConnectTimeout("slow"))
    with pytest.raises(ElexonUnavailableError, match="timeout"):
        client.fetch_wind_actuals(date(2026, 1, 1), date(2026, 1, 1))
    assert route.call_count == 3


@respx.mock
def test_network_error_is_unavailable(client):
    respx.get(f"{BASE}/datasets/FUELHH/stream").mock(side_effect=httpx.ConnectError("dns"))
    with pytest.raises(ElexonUnavailableError):
        client.fetch_wind_actuals(date(2026, 1, 1), date(2026, 1, 1))


@respx.mock
def test_client_error_is_not_retried(client):
    route = respx.get(f"{BASE}/datasets/FUELHH/stream").mock(return_value=httpx.Response(400, text="bad"))
    with pytest.raises(ElexonResponseError, match="400"):
        client.fetch_wind_actuals(date(2026, 1, 1), date(2026, 1, 1))
    assert route.call_count == 1


@respx.mock
def test_invalid_json_raises_response_error(client):
    respx.get(f"{BASE}/datasets/FUELHH/stream").mock(return_value=httpx.Response(200, text="<html>"))
    with pytest.raises(ElexonResponseError, match="invalid JSON"):
        client.fetch_wind_actuals(date(2026, 1, 1), date(2026, 1, 1))


@respx.mock
def test_unexpected_payload_shape_raises(client):
    respx.get(f"{BASE}/datasets/FUELHH/stream").mock(return_value=httpx.Response(200, json={"oops": 1}))
    with pytest.raises(ElexonResponseError, match="unexpected payload"):
        client.fetch_wind_actuals(date(2026, 1, 1), date(2026, 1, 1))


@respx.mock
def test_wrapped_data_payload_and_non_dict_rows(client):
    respx.get(f"{BASE}/datasets/FUELHH/stream").mock(return_value=httpx.Response(200, json={"data": [{"a": 1}, 5, None]}))
    assert client.fetch_wind_actuals(date(2026, 1, 1), date(2026, 1, 1)) == [{"a": 1}]
