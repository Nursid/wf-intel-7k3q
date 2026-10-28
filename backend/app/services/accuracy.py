"""Forecast accuracy metrics. These are computed only on MATCHED intervals; there is no zero-filling.

error = forecast - actual        (positive = over-forecast)
MAE   = mean(|error|)
RMSE  = sqrt(mean(error^2))
MBE   = mean(error)
WAPE  = sum(|error|) / sum(|actual|) * 100   (None when the denominator is 0)
Coverage = matched intervals / expected intervals in the selected delivery range.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from app.services.forecast_selector import (
    STATUS_MATCHED,
    STATUS_MISSING_ACTUAL,
    STATUS_MISSING_BOTH,
    STATUS_MISSING_FORECAST,
)


@dataclass
class AccuracyMetrics:
    mae_mw: float | None
    rmse_mw: float | None
    mbe_mw: float | None
    wape_pct: float | None
    matched_count: int
    missing_forecast_count: int
    missing_actual_count: int
    missing_both_count: int
    expected_count: int
    coverage_pct: float | None
    mean_forecast_mw: float | None
    mean_actual_mw: float | None
    max_abs_error_mw: float | None

    def as_dict(self) -> dict:
        return asdict(self)


def _clean(x: float) -> float | None:
    return None if x is None or not math.isfinite(x) else float(x)


def compute_metrics(forecast: np.ndarray | pd.Series, actual: np.ndarray | pd.Series) -> dict[str, float | None]:
    """Core error metrics on paired arrays. Pairs where either side is NaN are excluded."""
    f = np.asarray(forecast, dtype="float64")
    a = np.asarray(actual, dtype="float64")
    if f.shape != a.shape:
        raise ValueError("forecast and actual must have the same length")
    valid = np.isfinite(f) & np.isfinite(a)
    f, a = f[valid], a[valid]
    if f.size == 0:
        return {"mae_mw": None, "rmse_mw": None, "mbe_mw": None, "wape_pct": None, "n": 0}
    err = f - a
    denom = np.abs(a).sum()
    return {
        "mae_mw": _clean(np.abs(err).mean()),
        "rmse_mw": _clean(math.sqrt((err**2).mean())),
        "mbe_mw": _clean(err.mean()),
        "wape_pct": _clean(np.abs(err).sum() / denom * 100) if denom > 0 else None,
        "n": int(f.size),
    }


PERCENTILES = (5, 10, 25, 50, 75, 90, 95)
WITHIN_THRESHOLDS_MW = (500, 1000, 2000, 3000)


def _bin_width(span: float) -> float:
    """A round histogram bin width giving roughly 15-35 bins."""
    for w in (100, 250, 500, 1000, 2000, 5000):
        if span / w <= 35:
            return w
    return 10_000


def error_distribution(errors: np.ndarray | pd.Series) -> dict | None:
    """Spread of error (forecast - actual) across matched intervals, for planning around the forecast.

    `actual_ranges` restates percentiles as "actual relative to forecast" (= -error), e.g. the central
    80 % range is actual in [forecast - P90(error), forecast - P10(error)].
    These are empirical (in-sample) ranges for the selected period, not a probabilistic forecast.
    """
    e = np.asarray(errors, dtype="float64")
    e = e[np.isfinite(e)]
    if e.size == 0:
        return None
    pct = {p: float(np.percentile(e, p)) for p in PERCENTILES}
    width = _bin_width(float(e.max() - e.min()) or 1.0)
    lo = math.floor(e.min() / width) * width
    hi = math.ceil(e.max() / width) * width
    if hi == lo:
        hi = lo + width
    counts, edges = np.histogram(e, bins=np.arange(lo, hi + width, width))
    return {
        "n": int(e.size),
        "percentiles_mw": {f"p{p:02d}": v for p, v in pct.items()},
        "actual_ranges": [
            {"coverage_pct": 50, "low_mw": -pct[75], "high_mw": -pct[25]},
            {"coverage_pct": 80, "low_mw": -pct[90], "high_mw": -pct[10]},
            {"coverage_pct": 90, "low_mw": -pct[95], "high_mw": -pct[5]},
        ],
        "within": [
            {"threshold_mw": t, "pct": float((np.abs(e) <= t).mean() * 100)} for t in WITHIN_THRESHOLDS_MW
        ],
        "over_forecast_pct": float((e > 0).mean() * 100),
        "histogram": [
            {"low_mw": float(a), "high_mw": float(b), "count": int(c)} for a, b, c in zip(edges[:-1], edges[1:], counts)
        ],
        "bin_width_mw": width,
    }


def summarize(matched: pd.DataFrame) -> AccuracyMetrics:
    """Summarise a match_intervals() frame: metrics on MATCHED rows plus data-quality counts."""
    counts = matched["status"].value_counts()
    ok = matched[matched["status"] == STATUS_MATCHED]
    core = compute_metrics(ok["forecast_mw"], ok["actual_mw"])
    expected = len(matched)
    n = core["n"]
    # Missing counts are inclusive: an interval missing both sides counts in both totals.
    both = int(counts.get(STATUS_MISSING_BOTH, 0))
    return AccuracyMetrics(
        mae_mw=core["mae_mw"],
        rmse_mw=core["rmse_mw"],
        mbe_mw=core["mbe_mw"],
        wape_pct=core["wape_pct"],
        matched_count=n,
        missing_forecast_count=both + int(counts.get(STATUS_MISSING_FORECAST, 0)),
        missing_actual_count=both + int(counts.get(STATUS_MISSING_ACTUAL, 0)),
        missing_both_count=both,
        expected_count=expected,
        coverage_pct=(n / expected * 100) if expected else None,
        mean_forecast_mw=_clean(ok["forecast_mw"].mean()) if n else None,
        mean_actual_mw=_clean(ok["actual_mw"].mean()) if n else None,
        max_abs_error_mw=_clean(ok["abs_error_mw"].max()) if n else None,
    )
