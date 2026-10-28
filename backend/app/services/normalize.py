"""Validate raw Elexon records and convert them to typed, UTC-indexed DataFrames.

Invalid rows are dropped and counted, never zero-filled.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

import pandas as pd
from pydantic import BaseModel, ValidationError, field_validator

ACTUAL_COLUMNS = ["start_time_utc", "actual_mw"]
FORECAST_COLUMNS = ["start_time_utc", "publish_time_utc", "forecast_mw"]


class _Generation(BaseModel):
    generation: float

    @field_validator("generation", mode="before")
    @classmethod
    def _numeric(cls, v: Any) -> Any:
        # Reject booleans and non-numeric strings explicitly; pydantic would coerce "1"/True.
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ValueError("generation must be numeric")
        if not math.isfinite(v):
            raise ValueError("generation must be finite")
        return v


def _aware(v: datetime) -> datetime:
    if v.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return v


class RawActual(_Generation):
    startTime: datetime
    publishTime: datetime | None = None
    fuelType: str

    check_aware = field_validator("startTime")(_aware)


class RawForecast(_Generation):
    startTime: datetime
    publishTime: datetime

    check_aware = field_validator("startTime", "publishTime")(_aware)


@dataclass
class NormalizationReport:
    received: int = 0
    accepted: int = 0
    invalid: int = 0
    non_wind: int = 0
    duplicates: int = 0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


def normalize_actuals(raw: list[dict[str, Any]]) -> tuple[pd.DataFrame, NormalizationReport]:
    report = NormalizationReport(received=len(raw))
    rows = []
    for item in raw:
        try:
            rec = RawActual.model_validate(item)
        except ValidationError:
            report.invalid += 1
            continue
        if rec.fuelType.upper() != "WIND":
            report.non_wind += 1
            continue
        rows.append((rec.startTime, rec.publishTime, rec.generation))

    df = pd.DataFrame(rows, columns=["start_time_utc", "publish_time_utc", "actual_mw"])
    df["start_time_utc"] = pd.to_datetime(df["start_time_utc"], utc=True)
    df["publish_time_utc"] = pd.to_datetime(df["publish_time_utc"], utc=True)
    # If an interval was republished (revised), keep the latest publication.
    df = df.sort_values(["start_time_utc", "publish_time_utc"], na_position="first")
    before = len(df)
    df = df.drop_duplicates("start_time_utc", keep="last")
    report.duplicates = before - len(df)
    report.accepted = len(df)
    df = df[ACTUAL_COLUMNS].astype({"actual_mw": "float64"}).reset_index(drop=True)
    return df, report


def normalize_forecasts(raw: list[dict[str, Any]]) -> tuple[pd.DataFrame, NormalizationReport]:
    report = NormalizationReport(received=len(raw))
    rows = []
    for item in raw:
        try:
            rec = RawForecast.model_validate(item)
        except ValidationError:
            report.invalid += 1
            continue
        rows.append((rec.startTime, rec.publishTime, rec.generation))

    df = pd.DataFrame(rows, columns=FORECAST_COLUMNS)
    df["start_time_utc"] = pd.to_datetime(df["start_time_utc"], utc=True)
    df["publish_time_utc"] = pd.to_datetime(df["publish_time_utc"], utc=True)
    before = len(df)
    df = df.drop_duplicates(["start_time_utc", "publish_time_utc"], keep="last")
    report.duplicates = before - len(df)
    report.accepted = len(df)
    df = (
        df.astype({"forecast_mw": "float64"})
        .sort_values(["start_time_utc", "publish_time_utc"])
        .reset_index(drop=True)
    )
    return df, report
