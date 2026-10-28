"""Response schemas. All timestamps are timezone-aware UTC (serialised with a trailing Z)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

IntervalStatus = Literal["MATCHED", "MISSING_FORECAST", "MISSING_ACTUAL", "MISSING_BOTH"]


class DataSourceInfo(BaseModel):
    mode: Literal["LIVE", "DEMO FIXTURE"]
    provider: str = "Elexon BMRS (Insights API)"
    cache_status: Literal["memory", "disk", "network", "stale-disk", "fixture"] | None
    stale: bool = Field(description="True when serving an old cache because the latest fetch failed")
    fetched_at_utc: datetime = Field(description="When the dataset currently served was downloaded")
    last_successful_fetch_utc: datetime | None
    errors: list[str] = []


class CutoffPolicyOut(BaseModel):
    mode: Literal["relative", "absolute"]
    day_offset: int | None
    local_time: str | None = Field(description="HH:MM in Europe/London (relative mode)")
    decision_at_utc: datetime | None
    timezone: str = "Europe/London"
    description: str


class Period(BaseModel):
    start_date: date = Field(description="First delivery day (Europe/London)")
    end_date: date = Field(description="Last delivery day (Europe/London, inclusive)")
    start_utc: datetime
    end_utc: datetime = Field(description="Exclusive end")


class Metrics(BaseModel):
    mae_mw: float | None
    rmse_mw: float | None
    mbe_mw: float | None
    wape_pct: float | None = Field(description="null when the sum of actual generation is zero")
    matched_count: int
    missing_forecast_count: int = Field(description="Intervals without an eligible forecast (incl. missing both)")
    missing_actual_count: int = Field(description="Intervals without an actual (incl. missing both)")
    missing_both_count: int
    expected_count: int
    coverage_pct: float | None
    mean_forecast_mw: float | None
    mean_actual_mw: float | None
    max_abs_error_mw: float | None


class DatasetInfo(BaseModel):
    actual_rows: int
    forecast_rows: int
    forecast_publications: int
    settlement_from: str
    settlement_to: str
    publish_from_utc: str
    publish_to_utc: str
    normalization: dict[str, dict[str, int]]


class DataQuality(BaseModel):
    coverage_definition: str
    analysis_resolution_minutes: int
    actual_resolution_minutes: int
    normalization: dict[str, dict[str, int]]


class MetaResponse(BaseModel):
    product: str
    available_start_date: date
    available_end_date: date
    default_cutoff: CutoffPolicyOut
    analysis_resolution_minutes: int
    actual_resolution_minutes: int
    dataset: DatasetInfo
    data_source: DataSourceInfo
    assumptions: list[str]


class OverviewResponse(BaseModel):
    period: Period
    cutoff: CutoffPolicyOut
    metrics: Metrics
    data_quality: DataQuality
    data_source: DataSourceInfo


class TimeseriesPoint(BaseModel):
    start_time_utc: datetime
    cutoff_utc: datetime
    forecast_mw: float | None
    publish_time_utc: datetime | None
    actual_mw: float | None
    error_mw: float | None
    status: IntervalStatus


class ActualPoint(BaseModel):
    start_time_utc: datetime
    actual_mw: float


class TimeseriesResponse(BaseModel):
    period: Period
    cutoff: CutoffPolicyOut
    intervals: list[TimeseriesPoint] = Field(description="Hourly analysis grid (forecast resolution)")
    actuals_half_hourly: list[ActualPoint] = Field(description="All FUELHH WIND actuals in the period")
    data_source: DataSourceInfo


class IntervalRow(BaseModel):
    start_time_utc: datetime
    cutoff_utc: datetime
    publish_time_utc: datetime | None
    forecast_mw: float | None
    actual_mw: float | None
    error_mw: float | None
    abs_error_mw: float | None
    status: IntervalStatus
    eligible_versions: int
    total_versions: int
    lead_time_minutes: float | None = Field(description="cutoff - publish time")
    horizon_minutes: float | None = Field(description="delivery start - publish time")


class IntervalsResponse(BaseModel):
    period: Period
    cutoff: CutoffPolicyOut
    items: list[IntervalRow]
    page: int
    page_size: int
    total: int
    total_pages: int
    sort_by: str
    sort_dir: Literal["asc", "desc"]
    data_source: DataSourceInfo


class ForecastVersion(BaseModel):
    publish_time_utc: datetime
    forecast_mw: float
    eligible: bool
    selected: bool
    minutes_before_cutoff: float = Field(description="cutoff - publish time; negative = published after cutoff")
    horizon_minutes: float = Field(description="delivery start - publish time")


class ForecastHistoryResponse(BaseModel):
    start_time_utc: datetime
    cutoff_utc: datetime
    cutoff: CutoffPolicyOut
    actual_mw: float | None
    selected: ForecastVersion | None
    eligible_versions: int
    total_versions: int
    versions: list[ForecastVersion]
    data_source: DataSourceInfo


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
    data_mode: Literal["live", "fixture"]
    dataset_loaded: bool
    cache_fetched_at_utc: datetime | None


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody
