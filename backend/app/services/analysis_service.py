"""Orchestrates dataset -> cutoff selection -> matching -> metrics for one analysis query."""

from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass
from datetime import date

import pandas as pd

from app.services.accuracy import AccuracyMetrics, error_distribution, summarize
from app.services.data_repository import DataRepository, Dataset
from app.services.forecast_selector import (
    ANALYSIS_FREQ,
    CutoffPolicy,
    build_interval_grid,
    forecast_versions,
    local_day_bounds_utc,
    match_intervals,
    select_forecasts,
)

SORTABLE_COLUMNS = (
    "start_time_utc",
    "publish_time_utc",
    "forecast_mw",
    "actual_mw",
    "error_mw",
    "abs_error_mw",
    "status",
)


@dataclass(frozen=True)
class AnalysisQuery:
    """Decisions taken on decision_start..decision_end (Europe/London) under `policy`."""

    decision_start: date
    decision_end: date
    policy: CutoffPolicy

    @property
    def delivery_dates(self) -> tuple[date, date]:
        return self.policy.delivery_dates(self.decision_start, self.decision_end)


@dataclass
class AnalysisResult:
    query: AnalysisQuery
    intervals: pd.DataFrame  # one row per expected hourly delivery interval
    metrics: AccuracyMetrics
    distribution: dict | None  # error spread on matched intervals, see accuracy.error_distribution
    dataset: Dataset


class AnalysisService:
    def __init__(self, repository: DataRepository, cache_size: int = 64) -> None:
        self.repository = repository
        self._cache: OrderedDict[tuple, AnalysisResult] = OrderedDict()
        self._cache_size = cache_size
        self._lock = threading.Lock()

    def analyze(self, query: AnalysisQuery) -> AnalysisResult:
        dataset = self.repository.get()
        key = (query, dataset.meta.fetched_at_utc)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]

        grid = build_interval_grid(*query.delivery_dates, ANALYSIS_FREQ)
        selected = select_forecasts(dataset.forecasts, grid, query.policy)
        intervals = match_intervals(selected, dataset.actuals)
        matched_errors = intervals.loc[intervals["status"] == "MATCHED", "error_mw"]
        result = AnalysisResult(query, intervals, summarize(intervals), error_distribution(matched_errors), dataset)

        with self._lock:
            self._cache[key] = result
            while len(self._cache) > self._cache_size:
                self._cache.popitem(last=False)
        return result

    def half_hourly_actuals(self, query: AnalysisQuery) -> pd.DataFrame:
        a = self.repository.get().actuals
        start, end = local_day_bounds_utc(*query.delivery_dates)
        return a[(a["start_time_utc"] >= start) & (a["start_time_utc"] < end)]

    def intervals_page(
        self, query: AnalysisQuery, page: int, page_size: int, sort_by: str, sort_dir: str
    ) -> tuple[pd.DataFrame, int, AnalysisResult]:
        if sort_by not in SORTABLE_COLUMNS:
            raise ValueError(f"sort_by must be one of {', '.join(SORTABLE_COLUMNS)}")
        result = self.analyze(query)
        df = result.intervals.sort_values(
            [sort_by, "start_time_utc"] if sort_by != "start_time_utc" else ["start_time_utc"],
            ascending=sort_dir == "asc",
            na_position="last",
            kind="stable",
        )
        total = len(df)
        offset = (page - 1) * page_size
        return df.iloc[offset : offset + page_size], total, result

    def forecast_history(self, policy: CutoffPolicy, start_time_utc: pd.Timestamp) -> tuple[pd.DataFrame, float | None]:
        dataset = self.repository.get()
        versions = forecast_versions(dataset.forecasts, start_time_utc, policy)
        actual = dataset.actuals.loc[dataset.actuals["start_time_utc"] == start_time_utc, "actual_mw"]
        return versions, (float(actual.iloc[0]) if len(actual) else None)
