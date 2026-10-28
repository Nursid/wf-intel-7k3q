"""Application settings, loaded from environment variables (and an optional .env file)."""

from datetime import date, time
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_version: str = "0.1.0"

    elexon_base_url: str = "https://data.elexon.co.uk/bmrs/api/v1"
    http_timeout_s: float = 30.0
    http_max_retries: int = 3
    http_backoff_s: float = 1.0
    fetch_chunk_days: int = 7

    cache_dir: Path = Path("./.cache")
    # 0 = the disk cache never expires (January 2026 is historical data).
    cache_ttl_hours: float = 0
    data_mode: Literal["live", "fixture"] = "live"
    # Load the dataset in a background thread at startup instead of on the first request.
    warm_on_startup: bool = False

    cors_origins: str = "http://localhost:5173"

    # Pilot assumption (not a market rule): decide at 09:00 Europe/London the day before delivery.
    default_cutoff_day_offset: int = 1
    default_cutoff_time: time = time(9, 0)

    # Delivery window the product supports.
    analysis_start_date: date = date(2026, 1, 1)
    analysis_end_date: date = date(2026, 1, 31)
    # Forecasts published this many days before the first delivery day are downloaded too,
    # so early-January deliveries keep their December 2025 forecast history.
    forecast_publish_lookback_days: int = 8

    admin_token: str | None = None

    @field_validator("admin_token", mode="before")
    @classmethod
    def _empty_token_is_none(cls, v: object) -> object:
        return v or None

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
