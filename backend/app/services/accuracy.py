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
