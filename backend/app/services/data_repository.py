"""Loads the normalised January 2026 dataset and caches it in memory and on disk.

Resolution order: memory -> disk cache -> Elexon API. If the API fails but a disk cache exists
(even an expired one), that cache is served and the response is flagged as stale.
The source (live Elexon vs. DEMO FIXTURE) travels with the data, so the UI can always disclose it.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

import pandas as pd

from app.core.config import Settings
from app.services.elexon_client import ElexonClient, ElexonError, ElexonUnavailableError
from app.services.normalize import normalize_actuals, normalize_forecasts

logger = logging.getLogger(__name__)

LONDON = ZoneInfo("Europe/London")
CACHE_FORMAT_VERSION = 1
FIXTURE_PATH = Path(__file__).resolve().parent.parent / "data" / "demo_fixture.json"

Source = Literal["elexon-live", "fixture"]
CacheStatus = Literal["memory", "disk", "network", "stale-disk", "fixture"]


@dataclass
class DatasetMeta:
    source: Source
    fetched_at_utc: datetime
    actual_rows: int
    forecast_rows: int
    forecast_publications: int
    settlement_from: str
    settlement_to: str
    publish_from_utc: str
    publish_to_utc: str
    normalization: dict[str, dict[str, int]] = field(default_factory=dict)

    def to_json(self) -> dict:
        d = self.__dict__.copy()
        d["fetched_at_utc"] = self.fetched_at_utc.isoformat()
        return d

    @classmethod
    def from_json(cls, d: dict) -> DatasetMeta:
        d = dict(d)
        d["fetched_at_utc"] = datetime.fromisoformat(d["fetched_at_utc"])
        return cls(**d)


@dataclass
class Dataset:
    actuals: pd.DataFrame
    forecasts: pd.DataFrame
    meta: DatasetMeta


@dataclass
class RepositoryStatus:
    cache_status: CacheStatus | None = None
    last_successful_fetch_utc: datetime | None = None
    last_error: str | None = None
    last_error_at_utc: datetime | None = None


def _frames_to_payload(actuals: pd.DataFrame, forecasts: pd.DataFrame, meta: DatasetMeta) -> dict:
    def iso(s: pd.Series) -> list[str]:
        return s.dt.strftime("%Y-%m-%dT%H:%M:%SZ").tolist()

    return {
        "format_version": CACHE_FORMAT_VERSION,
        "meta": meta.to_json(),
        "actuals": {"start_time_utc": iso(actuals["start_time_utc"]), "actual_mw": actuals["actual_mw"].tolist()},
        "forecasts": {
            "start_time_utc": iso(forecasts["start_time_utc"]),
            "publish_time_utc": iso(forecasts["publish_time_utc"]),
            "forecast_mw": forecasts["forecast_mw"].tolist(),
        },
    }


def _payload_to_dataset(payload: dict) -> Dataset:
    if payload.get("format_version") != CACHE_FORMAT_VERSION:
        raise ValueError("unsupported cache format")
    a = pd.DataFrame(payload["actuals"])
    a["start_time_utc"] = pd.to_datetime(a["start_time_utc"], utc=True)
    a["actual_mw"] = a["actual_mw"].astype("float64")
    f = pd.DataFrame(payload["forecasts"])
    f["start_time_utc"] = pd.to_datetime(f["start_time_utc"], utc=True)
    f["publish_time_utc"] = pd.to_datetime(f["publish_time_utc"], utc=True)
    f["forecast_mw"] = f["forecast_mw"].astype("float64")
    return Dataset(a, f, DatasetMeta.from_json(payload["meta"]))


class DataRepository:
    def __init__(self, settings: Settings, client_factory=None) -> None:
        self._settings = settings
        self._client_factory = client_factory or self._default_client
        self._lock = threading.Lock()
        self._dataset: Dataset | None = None
        self.status = RepositoryStatus()

    # ------------------------------------------------------------------ windows

    def settlement_window(self) -> tuple:
        # Settlement dates are UK-local; pad by a day each side and trim on startTime later.
        s = self._settings
        return s.delivery_start_date - timedelta(days=1), s.delivery_end_date + timedelta(days=1)

    def publish_window(self) -> tuple[datetime, datetime]:
        # From well before the first decision (December history) to the end of the last delivery day,
        # so the version history also shows forecasts published after the cutoff.
        s = self._settings
        start_local = datetime.combine(
            s.decision_start_date - timedelta(days=s.forecast_publish_lookback_days),
            datetime.min.time(),
            tzinfo=LONDON,
        )
        end_local = datetime.combine(s.delivery_end_date + timedelta(days=1), datetime.min.time(), tzinfo=LONDON)
        return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)

    @property
    def cache_file(self) -> Path:
        s = self._settings
        return Path(s.cache_dir) / f"elexon_wind_decisions_{s.decision_start_date}_{s.decision_end_date}.json"

    # ------------------------------------------------------------------ public

    @property
    def loaded_meta(self) -> DatasetMeta | None:
        """Metadata of the in-memory dataset, without triggering a load."""
        return self._dataset.meta if self._dataset is not None else None

    def get(self) -> Dataset:
        with self._lock:
            if self._dataset is not None:
                if self.status.cache_status not in ("fixture", "stale-disk"):
                    self.status.cache_status = "memory"
                return self._dataset
            self._dataset = self._load()
            return self._dataset

    def refresh(self) -> Dataset:
        """Force a re-download from Elexon (live mode only)."""
        with self._lock:
            if self._settings.data_mode == "fixture":
                self._dataset = self._load_fixture()
            else:
                self._dataset = self._fetch_and_store()
            return self._dataset

    # ------------------------------------------------------------------ internals

    def _load(self) -> Dataset:
        if self._settings.data_mode == "fixture":
            return self._load_fixture()

        cached = self._read_disk()
        if cached is not None and not self._expired(cached.meta):
            self.status.cache_status = "disk"
            self.status.last_successful_fetch_utc = cached.meta.fetched_at_utc
            return cached

        try:
            return self._fetch_and_store()
        except ElexonError as exc:
            if cached is not None:
                logger.warning("Elexon fetch failed, serving stale cache: %s", exc)
                self.status.cache_status = "stale-disk"
                self.status.last_successful_fetch_utc = cached.meta.fetched_at_utc
                return cached
            raise

    def _expired(self, meta: DatasetMeta) -> bool:
        ttl = self._settings.cache_ttl_hours
        if ttl <= 0:
            return False
        return datetime.now(timezone.utc) - meta.fetched_at_utc > timedelta(hours=ttl)

    def _fetch_and_store(self) -> Dataset:
        s_from, s_to = self.settlement_window()
        p_from, p_to = self.publish_window()
        try:
            with self._client_factory() as client:
                raw_actuals = client.fetch_wind_actuals(s_from, s_to)
                raw_forecasts = client.fetch_wind_forecasts(p_from, p_to)
        except ElexonError as exc:
            self.status.last_error = str(exc)
            self.status.last_error_at_utc = datetime.now(timezone.utc)
            raise

        actuals, a_rep = normalize_actuals(raw_actuals)
        forecasts, f_rep = normalize_forecasts(raw_forecasts)
        if actuals.empty or forecasts.empty:
            msg = f"Elexon returned no usable data (actuals={len(actuals)}, forecasts={len(forecasts)})"
            self.status.last_error = msg
            self.status.last_error_at_utc = datetime.now(timezone.utc)
            raise ElexonUnavailableError(msg)

        now = datetime.now(timezone.utc)
        meta = DatasetMeta(
            source="elexon-live",
            fetched_at_utc=now,
            actual_rows=len(actuals),
            forecast_rows=len(forecasts),
            forecast_publications=int(forecasts["publish_time_utc"].nunique()),
            settlement_from=s_from.isoformat(),
            settlement_to=s_to.isoformat(),
            publish_from_utc=p_from.isoformat(),
            publish_to_utc=p_to.isoformat(),
            normalization={"actuals": a_rep.as_dict(), "forecasts": f_rep.as_dict()},
        )
        self._write_disk(actuals, forecasts, meta)
        self.status.cache_status = "network"
        self.status.last_successful_fetch_utc = now
        self.status.last_error = None
        self.status.last_error_at_utc = None
        return Dataset(actuals, forecasts, meta)

    def _read_disk(self) -> Dataset | None:
        path = self.cache_file
        if not path.exists():
            return None
        try:
            return _payload_to_dataset(json.loads(path.read_text(encoding="utf-8")))
        except Exception as exc:  # corrupt or outdated cache: ignore it, refetch
            logger.warning("Ignoring unreadable cache %s: %s", path, exc)
            return None

    def _write_disk(self, actuals: pd.DataFrame, forecasts: pd.DataFrame, meta: DatasetMeta) -> None:
        path = self.cache_file
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(_frames_to_payload(actuals, forecasts, meta)), encoding="utf-8")
            tmp.replace(path)
        except OSError as exc:  # a read-only filesystem must not break serving
            logger.warning("Could not write cache %s: %s", path, exc)

    def _load_fixture(self) -> Dataset:
        ds = _payload_to_dataset(json.loads(FIXTURE_PATH.read_text(encoding="utf-8")))
        if ds.meta.source != "fixture":
            raise ValueError("demo fixture must be labelled source='fixture'")
        self.status.cache_status = "fixture"
        self.status.last_successful_fetch_utc = ds.meta.fetched_at_utc
        return ds

    def _default_client(self) -> ElexonClient:
        s = self._settings
        return ElexonClient(
            base_url=s.elexon_base_url,
            timeout_s=s.http_timeout_s,
            max_retries=s.http_max_retries,
            backoff_s=s.http_backoff_s,
            chunk_days=s.fetch_chunk_days,
        )


__all__ = ["DataRepository", "Dataset", "DatasetMeta", "ElexonUnavailableError", "FIXTURE_PATH"]
