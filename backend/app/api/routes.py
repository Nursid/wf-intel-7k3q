"""HTTP routes. Query parameters are validated here, and all business logic lives in services."""

from __future__ import annotations

import math
import re
from datetime import date, datetime, time
from typing import Annotated, Any, Literal

import pandas as pd
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request

from app.core.config import Settings
from app.schemas.analysis import (
    CutoffPolicyOut,
    DataQuality,
    DatasetInfo,
    DataSourceInfo,
    ErrorDistribution,
    ErrorResponse,
    ForecastHistoryResponse,
    ForecastVersion,
    HealthResponse,
    IntervalRow,
    IntervalsResponse,
    MetaResponse,
    Metrics,
    OverviewResponse,
    Period,
    TimeseriesPoint,
    TimeseriesResponse,
    ActualPoint,
)
from app.services.analysis_service import AnalysisQuery, AnalysisService
from app.services.data_repository import Dataset
from app.services.forecast_selector import (
    ACTUAL_FREQ,
    ANALYSIS_FREQ,
    CutoffPolicy,
    local_day_bounds_utc,
)

router = APIRouter()
ERRORS = {422: {"model": ErrorResponse}, 503: {"model": ErrorResponse}}
HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

COVERAGE_DEFINITION = (
    "Matched intervals ÷ expected hourly delivery intervals for the delivery days covered by the selected "
    "decision dates (Europe/London). WINDFOR forecasts are hourly, so each hour is matched to the FUELHH "
    "actual starting at the same time."
)
ASSUMPTIONS = [
    "Scope follows the brief: purchase decisions made in January 2026. With the day-ahead default, "
    "decisions on 1–31 Jan cover deliveries on 2 Jan – 1 Feb.",
    "The default decision time (D-1 at 09:00 Europe/London) is a configurable pilot assumption, "
    "not a regulatory or trading deadline. Confirm it against the auction the team uses.",
    "A forecast is used only if it was published at or before the decision cutoff and at or before the "
    "start of the delivery hour. Nothing published later is ever used.",
    "WINDFOR is published at hourly resolution, so accuracy is assessed on hourly delivery intervals "
    "against the FUELHH half-hour starting at the same time. Forecasts are not interpolated.",
    "Error ranges (e.g. P10–P90) are empirical, from the matched hours of the selected period. They "
    "describe past performance and are not a probabilistic forecast.",
    "Missing forecasts or actuals are excluded from metrics and disclosed. They are never treated as zero.",
    "Scope is national wind only (Elexon FUELHH + WINDFOR). The tool does not recommend purchase volumes.",
]


# ---------------------------------------------------------------- dependencies


def get_service(request: Request) -> AnalysisService:
    return request.app.state.analysis_service


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def _bad(msg: str) -> HTTPException:
    return HTTPException(status_code=422, detail=msg)


def analysis_query(
    settings: Annotated[Settings, Depends(get_settings_dep)],
    decision_start_date: Annotated[date | None, Query(description="First decision day, Europe/London")] = None,
    decision_end_date: Annotated[date | None, Query(description="Last decision day (inclusive), Europe/London")] = None,
    cutoff_day_offset: Annotated[int | None, Query(description="Decide this many days before delivery (1 = day-ahead)")] = None,
    cutoff_time: Annotated[str | None, Query(description="Decision time HH:MM, Europe/London")] = None,
) -> AnalysisQuery:
    lo, hi = settings.decision_start_date, settings.decision_end_date
    start = decision_start_date or lo
    end = decision_end_date or hi
    if not (lo <= start <= hi) or not (lo <= end <= hi):
        raise _bad(f"Decision dates must be between {lo} and {hi}")
    if end < start:
        raise _bad("decision_end_date must be on or after decision_start_date")

    offset = settings.default_cutoff_day_offset if cutoff_day_offset is None else cutoff_day_offset
    if not 0 <= offset <= settings.max_day_offset:
        raise _bad(f"cutoff_day_offset must be between 0 and {settings.max_day_offset}")
    if cutoff_time is None:
        local_t = settings.default_cutoff_time
    elif HHMM.match(cutoff_time):
        local_t = time.fromisoformat(cutoff_time)
    else:
        raise _bad("cutoff_time must be HH:MM (24h)")
    return AnalysisQuery(start, end, CutoffPolicy(day_offset=offset, local_time=local_t))


QueryDep = Annotated[AnalysisQuery, Depends(analysis_query)]
ServiceDep = Annotated[AnalysisService, Depends(get_service)]


# ---------------------------------------------------------------- helpers


def _num(v: Any) -> float | None:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    return float(v)


def _ts(v: Any) -> datetime | None:
    return None if v is None or pd.isna(v) else pd.Timestamp(v).to_pydatetime()


def policy_out(p: CutoffPolicy) -> CutoffPolicyOut:
    return CutoffPolicyOut(day_offset=p.day_offset, local_time=p.local_time.strftime("%H:%M"), description=p.describe())


def period_out(q: AnalysisQuery) -> Period:
    d_start, d_end = q.delivery_dates
    s, e = local_day_bounds_utc(d_start, d_end)
    return Period(
        decision_start_date=q.decision_start,
        decision_end_date=q.decision_end,
        delivery_start_date=d_start,
        delivery_end_date=d_end,
        start_utc=s.to_pydatetime(),
        end_utc=e.to_pydatetime(),
    )


def data_source_out(service: AnalysisService, dataset: Dataset) -> DataSourceInfo:
    st = service.repository.status
    return DataSourceInfo(
        mode="DEMO FIXTURE" if dataset.meta.source == "fixture" else "LIVE",
        cache_status=st.cache_status,
        stale=st.cache_status == "stale-disk",
        fetched_at_utc=dataset.meta.fetched_at_utc,
        last_successful_fetch_utc=st.last_successful_fetch_utc,
        errors=[st.last_error] if st.last_error else [],
    )


def _interval_row(r: dict) -> IntervalRow:
    return IntervalRow(
        start_time_utc=_ts(r["start_time_utc"]),
        cutoff_utc=_ts(r["cutoff_utc"]),
        publish_time_utc=_ts(r["publish_time_utc"]),
        forecast_mw=_num(r["forecast_mw"]),
        actual_mw=_num(r["actual_mw"]),
        error_mw=_num(r["error_mw"]),
        abs_error_mw=_num(r["abs_error_mw"]),
        status=r["status"],
        eligible_versions=int(r["eligible_versions"]),
        total_versions=int(r["total_versions"]),
        lead_time_minutes=_num(r["lead_time_minutes"]),
        horizon_minutes=_num(r["horizon_minutes"]),
    )


# ---------------------------------------------------------------- routes


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health(service: ServiceDep, settings: Annotated[Settings, Depends(get_settings_dep)]) -> HealthResponse:
    meta = service.repository.loaded_meta
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        data_mode=settings.data_mode,
        dataset_loaded=meta is not None,
        cache_fetched_at_utc=meta.fetched_at_utc if meta else None,
    )


@router.get("/api/meta", response_model=MetaResponse, responses=ERRORS, tags=["analysis"])
def meta(service: ServiceDep, settings: Annotated[Settings, Depends(get_settings_dep)]) -> MetaResponse:
    ds = service.repository.get()
    default = CutoffPolicy(day_offset=settings.default_cutoff_day_offset, local_time=settings.default_cutoff_time)
    m = ds.meta
    return MetaResponse(
        product="Wind Forecast Intelligence",
        decision_start_date=settings.decision_start_date,
        decision_end_date=settings.decision_end_date,
        max_day_offset=settings.max_day_offset,
        default_cutoff=policy_out(default),
        analysis_resolution_minutes=int(ANALYSIS_FREQ.total_seconds() // 60),
        actual_resolution_minutes=int(ACTUAL_FREQ.total_seconds() // 60),
        dataset=DatasetInfo(
            actual_rows=m.actual_rows, forecast_rows=m.forecast_rows, forecast_publications=m.forecast_publications,
            settlement_from=m.settlement_from, settlement_to=m.settlement_to,
            publish_from_utc=m.publish_from_utc, publish_to_utc=m.publish_to_utc, normalization=m.normalization,
        ),
        data_source=data_source_out(service, ds),
        assumptions=ASSUMPTIONS,
    )


@router.get("/api/analysis/overview", response_model=OverviewResponse, responses=ERRORS, tags=["analysis"])
def overview(q: QueryDep, service: ServiceDep) -> OverviewResponse:
    r = service.analyze(q)
    return OverviewResponse(
        period=period_out(q),
        cutoff=policy_out(q.policy),
        metrics=Metrics(**r.metrics.as_dict()),
        error_distribution=ErrorDistribution(**r.distribution) if r.distribution else None,
        data_quality=DataQuality(
            coverage_definition=COVERAGE_DEFINITION,
            analysis_resolution_minutes=int(ANALYSIS_FREQ.total_seconds() // 60),
            actual_resolution_minutes=int(ACTUAL_FREQ.total_seconds() // 60),
            normalization=r.dataset.meta.normalization,
        ),
        data_source=data_source_out(service, r.dataset),
    )


@router.get("/api/analysis/timeseries", response_model=TimeseriesResponse, responses=ERRORS, tags=["analysis"])
def timeseries(q: QueryDep, service: ServiceDep) -> TimeseriesResponse:
    r = service.analyze(q)
    # Central 80 % range for actual around each forecast: actual = forecast - error.
    pct = r.distribution["percentiles_mw"] if r.distribution else None

    def band(f: float | None, p: str) -> float | None:
        # Generation cannot be negative, so the range is floored at 0 MW.
        return None if f is None or pct is None else max(0.0, f - pct[p])

    points = [
        TimeseriesPoint(
            start_time_utc=_ts(row["start_time_utc"]),
            cutoff_utc=_ts(row["cutoff_utc"]),
            forecast_mw=_num(row["forecast_mw"]),
            publish_time_utc=_ts(row["publish_time_utc"]),
            actual_mw=_num(row["actual_mw"]),
            error_mw=_num(row["error_mw"]),
            status=row["status"],
            range_low_mw=band(_num(row["forecast_mw"]), "p90"),
            range_high_mw=band(_num(row["forecast_mw"]), "p10"),
        )
        for row in r.intervals.to_dict("records")
    ]
    actuals = [
        ActualPoint(start_time_utc=_ts(row["start_time_utc"]), actual_mw=float(row["actual_mw"]))
        for row in service.half_hourly_actuals(q).to_dict("records")
    ]
    return TimeseriesResponse(
        period=period_out(q), cutoff=policy_out(q.policy), intervals=points,
        actuals_half_hourly=actuals, data_source=data_source_out(service, r.dataset),
    )


@router.get("/api/analysis/intervals", response_model=IntervalsResponse, responses=ERRORS, tags=["analysis"])
def intervals(
    q: QueryDep,
    service: ServiceDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=500)] = 50,
    sort_by: Annotated[str, Query()] = "start_time_utc",
    sort_dir: Annotated[Literal["asc", "desc"], Query()] = "asc",
) -> IntervalsResponse:
    try:
        rows, total, r = service.intervals_page(q, page, page_size, sort_by, sort_dir)
    except ValueError as exc:
        raise _bad(str(exc)) from exc
    return IntervalsResponse(
        period=period_out(q),
        cutoff=policy_out(q.policy),
        items=[_interval_row(x) for x in rows.to_dict("records")],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=max(1, math.ceil(total / page_size)),
        sort_by=sort_by,
        sort_dir=sort_dir,
        data_source=data_source_out(service, r.dataset),
    )


@router.get(
    "/api/analysis/forecast-history", response_model=ForecastHistoryResponse, responses=ERRORS, tags=["analysis"]
)
def forecast_history(
    q: QueryDep,
    service: ServiceDep,
    start_time: Annotated[datetime, Query(description="Delivery interval start, ISO datetime with offset")],
) -> ForecastHistoryResponse:
    if start_time.tzinfo is None:
        raise _bad("start_time must include a timezone offset")
    ts = pd.Timestamp(start_time).tz_convert("UTC")
    lo, hi = local_day_bounds_utc(*q.delivery_dates)
    if not lo <= ts < hi:
        raise _bad("start_time is outside the delivery days covered by the selected decision dates")
    if ts.floor(ANALYSIS_FREQ) != ts:
        raise _bad("start_time must be on an hourly forecast interval boundary")

    versions, actual = service.forecast_history(q.policy, ts)
    cutoff = q.policy.cutoff_for(ts.to_pydatetime())
    items = [
        ForecastVersion(
            publish_time_utc=_ts(v["publish_time_utc"]),
            forecast_mw=float(v["forecast_mw"]),
            eligible=bool(v["eligible"]),
            selected=bool(v["selected"]),
            ineligible_reason=v["ineligible_reason"],
            minutes_before_cutoff=(pd.Timestamp(cutoff) - v["publish_time_utc"]).total_seconds() / 60,
            horizon_minutes=(ts - v["publish_time_utc"]).total_seconds() / 60,
        )
        for v in versions.to_dict("records")
    ]
    selected = next((v for v in items if v.selected), None)
    return ForecastHistoryResponse(
        start_time_utc=ts.to_pydatetime(),
        cutoff_utc=cutoff,
        cutoff=policy_out(q.policy),
        actual_mw=actual,
        selected=selected,
        eligible_versions=sum(v.eligible for v in items),
        total_versions=len(items),
        versions=items,
        data_source=data_source_out(service, service.repository.get()),
    )


@router.post("/api/admin/refresh", response_model=MetaResponse, responses=ERRORS, tags=["system"])
def refresh(
    service: ServiceDep,
    settings: Annotated[Settings, Depends(get_settings_dep)],
    x_admin_token: Annotated[str | None, Header()] = None,
) -> MetaResponse:
    if not settings.admin_token:
        raise HTTPException(status_code=404, detail="Refresh endpoint is disabled")
    if x_admin_token != settings.admin_token:
        raise HTTPException(status_code=403, detail="Invalid admin token")
    service.repository.refresh()
    return meta(service, settings)
