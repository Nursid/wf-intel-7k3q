"""Shared deterministic TEST fixtures. These are synthetic and never used as production data."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.data_repository import DataRepository


def ts(s: str) -> pd.Timestamp:
    return pd.Timestamp(s).tz_convert("UTC") if pd.Timestamp(s).tzinfo else pd.Timestamp(s, tz="UTC")


def forecasts_df(rows: list[tuple[str, str, float]]) -> pd.DataFrame:
    """rows: (start_time, publish_time, forecast_mw)"""
    return pd.DataFrame(
        {
            "start_time_utc": [ts(r[0]) for r in rows],
            "publish_time_utc": [ts(r[1]) for r in rows],
            "forecast_mw": [float(r[2]) for r in rows],
        }
    )


def actuals_df(rows: list[tuple[str, float]]) -> pd.DataFrame:
    return pd.DataFrame({"start_time_utc": [ts(r[0]) for r in rows], "actual_mw": [float(r[1]) for r in rows]})


# ---------------------------------------------------------------- synthetic "Elexon" source for API tests

SYN_START = datetime(2026, 1, 2, tzinfo=timezone.utc)
MISSING_FORECAST_HOUR = datetime(2026, 1, 3, 5, tzinfo=timezone.utc)
MISSING_ACTUAL_HOUR = datetime(2026, 1, 3, 6, tzinfo=timezone.utc)


def _z(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def synthetic_raw() -> tuple[list[dict], list[dict]]:
    """Deliveries 2-3 Jan 2026, i.e. day-ahead decisions on 1-2 Jan (GMT, so local == UTC).

    Actuals: half-hourly, generation = 1000 + index. The 06:00 slot on 3 Jan is missing.
    Forecasts per hour, four versions:
      D-2 08:00Z     -> actual + 100
      D-1 08:30Z     -> actual + 50   (latest before the default cutoff D-1 09:00)
      D-1 10:00Z     -> actual + 10   (after cutoff: never selected under the default)
      start + 30 min -> actual + 1    ("nowcast" published after the hour began: never eligible)
    The 05:00 hour on 3 Jan has no forecasts.
    """
    actuals, forecasts = [], []
    for i in range(96):
        start = SYN_START + timedelta(minutes=30 * i)
        if start == MISSING_ACTUAL_HOUR:
            continue
        actuals.append({"startTime": _z(start), "publishTime": _z(start + timedelta(minutes=30)),
                        "fuelType": "WIND", "generation": 1000 + i})
        actuals.append({"startTime": _z(start), "publishTime": _z(start), "fuelType": "CCGT", "generation": 5})
    for h in range(48):
        start = SYN_START + timedelta(hours=h)
        if start == MISSING_FORECAST_HOUR:
            continue
        base = 1000 + 2 * h
        day = start.replace(hour=0)
        for pub, delta in ((day - timedelta(days=2, hours=-8), 100),
                           (day - timedelta(days=1, hours=-8, minutes=-30), 50),
                           (day - timedelta(days=1, hours=-10), 10),
                           (start + timedelta(minutes=30), 1)):
            forecasts.append({"startTime": _z(start), "publishTime": _z(pub), "generation": base + delta})
    return actuals, forecasts


class FakeClient:
    def __init__(self, fail: Exception | None = None, raw=None) -> None:
        self.fail = fail
        self.raw = raw or synthetic_raw()
        self.calls = 0

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def fetch_wind_actuals(self, *_):
        self.calls += 1
        if self.fail:
            raise self.fail
        return self.raw[0]

    def fetch_wind_forecasts(self, *_):
        if self.fail:
            raise self.fail
        return self.raw[1]


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        cache_dir=tmp_path / "cache",
        data_mode="live",
        decision_start_date=date(2026, 1, 1),
        decision_end_date=date(2026, 1, 31),
        admin_token="secret",
    )


@pytest.fixture
def fake_client() -> FakeClient:
    return FakeClient()


@pytest.fixture
def client(settings, fake_client) -> TestClient:
    repo = DataRepository(settings, client_factory=lambda: fake_client)
    return TestClient(create_app(settings, repo))
