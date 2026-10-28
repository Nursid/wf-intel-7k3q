import math

import numpy as np
import pandas as pd
import pytest

from app.services.accuracy import compute_metrics, summarize


# 6. hand-calculated metric values
def test_metrics_symmetric_errors():
    m = compute_metrics([110, 90, 100], [100, 100, 100])
    assert m["mae_mw"] == pytest.approx(20 / 3)
    assert m["rmse_mw"] == pytest.approx(math.sqrt(200 / 3))
    assert m["mbe_mw"] == pytest.approx(0)
    assert m["wape_pct"] == pytest.approx(20 / 300 * 100)
    assert m["n"] == 3


def test_metrics_over_forecast_bias_is_positive():
    m = compute_metrics([120, 130], [100, 100])
    assert m["mae_mw"] == 25
    assert m["mbe_mw"] == 25
    assert m["rmse_mw"] == pytest.approx(math.sqrt((400 + 900) / 2))
    assert m["wape_pct"] == pytest.approx(25.0)


def test_metrics_under_forecast_bias_is_negative():
    assert compute_metrics([80], [100])["mbe_mw"] == -20


# 7. zero actuals / zero WAPE denominator
def test_wape_unavailable_when_actual_sum_is_zero():
    m = compute_metrics([10, 0], [0, 0])
    assert m["wape_pct"] is None
    assert m["mae_mw"] == 5


def test_zero_actual_in_some_intervals_still_counts():
    m = compute_metrics([10, 110], [0, 100])
    assert m["wape_pct"] == pytest.approx(20 / 100 * 100)


# 8. invalid / missing values are excluded, not zero-filled
def test_nan_pairs_are_excluded():
    m = compute_metrics([110, np.nan, 100, np.inf], [100, 100, np.nan, 100])
    assert m["n"] == 1 and m["mae_mw"] == 10


def test_no_valid_pairs_returns_none_not_zero():
    m = compute_metrics([np.nan], [100])
    assert m == {"mae_mw": None, "rmse_mw": None, "mbe_mw": None, "wape_pct": None, "n": 0}


def test_length_mismatch_raises():
    with pytest.raises(ValueError):
        compute_metrics([1, 2], [1])


def test_summarize_counts_and_coverage():
    df = pd.DataFrame(
        {
            "status": ["MATCHED", "MATCHED", "MISSING_FORECAST", "MISSING_ACTUAL", "MISSING_BOTH"],
            "forecast_mw": [110, 90, np.nan, 50, np.nan],
            "actual_mw": [100, 100, 70, np.nan, np.nan],
        }
    )
    df["abs_error_mw"] = (df.forecast_mw - df.actual_mw).abs()
    s = summarize(df)
    assert s.matched_count == 2 and s.expected_count == 5
    assert s.missing_forecast_count == 2  # MISSING_FORECAST + MISSING_BOTH
    assert s.missing_actual_count == 2
    assert s.missing_both_count == 1
    assert s.coverage_pct == pytest.approx(40)
    assert s.mae_mw == 10 and s.mbe_mw == 0
    assert s.mean_actual_mw == 100  # matched rows only, the 70 MW unmatched actual is excluded
    assert s.max_abs_error_mw == 10


def test_summarize_with_nothing_matched():
    df = pd.DataFrame({"status": ["MISSING_FORECAST"], "forecast_mw": [np.nan], "actual_mw": [5.0], "abs_error_mw": [np.nan]})
    s = summarize(df)
    assert s.mae_mw is None and s.mean_forecast_mw is None and s.coverage_pct == 0
