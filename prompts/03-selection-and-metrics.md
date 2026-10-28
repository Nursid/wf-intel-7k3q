# Phase 3 — Cutoff-aware Forecast Selection + Accuracy Metrics

## Goal
Implement the core business logic as pure, fully tested functions.

## Files
```
backend/app/services/forecast_selector.py
backend/app/services/accuracy.py
backend/tests/test_forecast_selector.py
backend/tests/test_accuracy.py
```

## Three timestamps (keep them distinct in code and naming)
- **Decision cutoff:** when the procurement decision is made
- **Publish time:** when a forecast became available
- **Delivery start:** the 30-minute interval being forecast

## Cutoff policy
- **Relative policy (default):** for each delivery interval, cutoff = `delivery date (Europe/London) − N days at HH:MM Europe/London`, converted to UTC. Defaults come from config.
- **Absolute policy:** a single explicit decision timestamp applies to every interval in the range.
- Convert in a DST-safe way with `zoneinfo`. Note that January is GMT (UTC+0), but the code must still be correct across DST changes.

## Selection algorithm (per delivery interval)
1. Take the forecasts for that `start_time_utc`.
2. Keep only rows with `publish_time_utc <= cutoff_utc`.
3. Pick the row with the latest `publish_time_utc`.
4. Record `eligible_versions_count`, `selected_publish_time`, and `lead_time = cutoff − publish_time`.
5. If nothing is eligible, mark `MISSING_FORECAST` (never fall back to a later forecast).

## Matching
- Build the **expected interval grid**: every 30-minute UTC slot in the selected delivery range (Europe/London calendar days → UTC).
- Join the selected forecast and the actual on `start_time_utc`.
- Status per interval: `MATCHED` | `MISSING_FORECAST` | `MISSING_ACTUAL` | `MISSING_BOTH`.

## Metrics (`accuracy.py`)
Use the definitions in CLAUDE.md. Compute them **on MATCHED rows only**. Return:
`mae, rmse, mbe, wape (nullable), matched_count, missing_forecast_count, missing_actual_count, expected_count, coverage_pct, total_forecast_mwh, total_actual_mwh` (MWh = Σ MW × 0.5 h, labelled as such).
If there are no matched rows, every metric returns `null`, never 0.

## Required tests (small deterministic fixtures, kept in `tests/fixtures/`)
1. Latest eligible forecast before the cutoff is selected
2. A forecast published after the cutoff is excluded, including one published exactly 1 second after
3. Several forecasts for the same interval
4. Missing forecast and missing actual records
5. Matching by delivery interval
6. MAE, RMSE, MBE, and WAPE against hand-calculated values
7. Zero actual generation, and WAPE returning null on a zero denominator
8. Invalid or missing numeric values excluded and counted
9. UTC vs Europe/London: cutoff conversion around the BST change (e.g. 29 March 2026) and in January
10. Publish time exactly equal to the cutoff counts as eligible (document this boundary rule)

## Exit check
- [ ] All tests pass
- [ ] Run against real cached January 2026 data. Report overall MAE, RMSE, MBE, WAPE, and coverage for the default cutoff, labelled as real computed output.

Stop and report.
