"""HTTP client for the Elexon Insights API (FUELHH and WINDFOR stream endpoints).

Verified behaviour (see docs/elexon-api-findings.md):
- /stream endpoints return a bare JSON array, with no pagination and no authentication.
- FUELHH filters on settlementDateFrom/To (inclusive, yyyy-MM-dd) and fuelType.
- WINDFOR filters on publishDateTimeFrom/To only.
Large ranges are split into chunks, so no single request depends on undocumented size limits.
"""

from __future__ import annotations

import logging
import time as _time
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class ElexonError(Exception):
    """Base class for Elexon integration errors."""


class ElexonUnavailableError(ElexonError):
    """Source unreachable: network failure, timeout, or retryable status after all retries."""


class ElexonResponseError(ElexonError):
    """Source answered, but with a non-retryable error or an unexpected payload."""


def _iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ElexonClient:
    def __init__(
        self,
        base_url: str,
        timeout_s: float = 30.0,
        max_retries: int = 3,
        backoff_s: float = 1.0,
        chunk_days: int = 7,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = _time.sleep,
    ) -> None:
        if chunk_days < 1:
            raise ValueError("chunk_days must be >= 1")
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout_s,
            transport=transport,
            headers={"Accept": "application/json"},
        )
        self._max_retries = max_retries
        self._backoff_s = backoff_s
        self._chunk_days = chunk_days
        self._sleep = sleep

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> ElexonClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------ public API

    def fetch_wind_actuals(self, settlement_from: date, settlement_to: date) -> list[dict[str, Any]]:
        """Raw FUELHH WIND records for settlement dates in [settlement_from, settlement_to] (inclusive)."""
        if settlement_to < settlement_from:
            raise ValueError("settlement_to must be >= settlement_from")
        rows: list[dict[str, Any]] = []
        chunk_start = settlement_from
        while chunk_start <= settlement_to:
            chunk_end = min(chunk_start + timedelta(days=self._chunk_days - 1), settlement_to)
            rows += self._get(
                "/datasets/FUELHH/stream",
                {
                    "settlementDateFrom": chunk_start.isoformat(),
                    "settlementDateTo": chunk_end.isoformat(),
                    "fuelType": "WIND",
                },
            )
            chunk_start = chunk_end + timedelta(days=1)
        return rows

    def fetch_wind_forecasts(self, publish_from: datetime, publish_to: datetime) -> list[dict[str, Any]]:
        """Raw WINDFOR records published within [publish_from, publish_to].

        Chunk boundaries may be returned twice; duplicates are removed during normalisation.
        """
        if publish_from.tzinfo is None or publish_to.tzinfo is None:
            raise ValueError("publish window must be timezone-aware")
        if publish_to < publish_from:
            raise ValueError("publish_to must be >= publish_from")
        rows: list[dict[str, Any]] = []
        chunk_start = publish_from
        while chunk_start < publish_to:
            chunk_end = min(chunk_start + timedelta(days=self._chunk_days), publish_to)
            rows += self._get(
                "/datasets/WINDFOR/stream",
                {"publishDateTimeFrom": _iso_z(chunk_start), "publishDateTimeTo": _iso_z(chunk_end)},
            )
            chunk_start = chunk_end
        return rows

    # ------------------------------------------------------------------ transport

    def _get(self, path: str, params: dict[str, str]) -> list[dict[str, Any]]:
        last_error: str = "unknown error"
        for attempt in range(self._max_retries + 1):
            if attempt:
                self._sleep(self._backoff_s * 2 ** (attempt - 1))
            try:
                resp = self._client.get(path, params=params)
            except httpx.TimeoutException:
                last_error = f"timeout calling {path}"
                logger.warning("%s (attempt %d)", last_error, attempt + 1)
                continue
            except httpx.TransportError as exc:
                last_error = f"network error calling {path}: {exc}"
                logger.warning("%s (attempt %d)", last_error, attempt + 1)
                continue

            if resp.status_code in RETRYABLE_STATUS:
                last_error = f"HTTP {resp.status_code} from {path}"
                logger.warning("%s (attempt %d)", last_error, attempt + 1)
                continue
            if resp.status_code >= 400:
                raise ElexonResponseError(f"HTTP {resp.status_code} from {path}: {resp.text[:200]}")
            return self._parse(resp, path)

        raise ElexonUnavailableError(f"{last_error} after {self._max_retries + 1} attempts")

    @staticmethod
    def _parse(resp: httpx.Response, path: str) -> list[dict[str, Any]]:
        try:
            body = resp.json()
        except ValueError as exc:
            raise ElexonResponseError(f"invalid JSON from {path}") from exc
        # /stream returns a bare array; the non-stream variants wrap it in {"data": [...]}.
        if isinstance(body, dict) and isinstance(body.get("data"), list):
            body = body["data"]
        if not isinstance(body, list):
            raise ElexonResponseError(f"unexpected payload type {type(body).__name__} from {path}")
        return [row for row in body if isinstance(row, dict)]
