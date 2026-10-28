# Phase 6 — Dashboard Features

## Goal
Build every dashboard widget on real API data, using the Phase 5 design system.

## Page layout (desktop)
```
┌──────────────────────────────── Header ────────────────────────────────┐
├──────────────────────────────── Filter bar ────────────────────────────┤
│ [KPI Forecast] [KPI Actual] [KPI MAE] [KPI Bias] [KPI Coverage]         │
├──────────── Forecast vs Actual chart (8 col) ───┬── Accuracy (4 col) ──┤
│                                                  │ MAE·RMSE·MBE·WAPE    │
├──────────── Interval table (8 col) ─────────────┼── Selected interval ─┤
│                                                  │ + forecast history   │
├──────────────────────────── Data quality ──────────────────────────────┤
```
On tablet, the layout stacks into a single column.

## 1. Filter bar (`components/filters/`)
- Delivery date range: date inputs restricted to 2026-01-01 → 2026-01-31, with presets *Full month*, *Week 1–4*, and *Single day*.
- Cutoff policy:
  - **Relative:** "Day before delivery" offset + time picker (Europe/London)
  - **Absolute:** a specific decision date/time
  - Helper text explains the policy and that the default is a pilot assumption
- **Apply** (or debounced auto-apply) and **Reset filters** (restores the defaults).
- Sync the filter state to the URL query string so views can be shared.
- Changing a filter must refetch all widgets.

## 2. KPI cards
Selected forecast total, actual total (labelled MWh, or average MW; be consistent), MAE (MW), Bias/MBE (MW, with an ↑ over or ↓ under badge), and Coverage (% + `matched / expected`).
Show `—` plus a reason tooltip for unavailable values. Never show a fake 0.

## 3. Forecast vs Actual chart (Recharts)
- Line chart: forecast (blue, dashed) and actual (green, solid). The y-axis is MW. The x-axis shows 30-minute ticks, auto-thinned for long ranges.
- Optional toggle for an error area/bar series.
- Tooltip shows the local time with its timezone label, forecast, actual, error (signed and coloured), and the publish time of the selected forecast.
- Missing points show as **gaps** (`connectNulls={false}`), not zero.
- Clicking a point selects that interval for the history panel.
- Includes a legend plus loading, empty, and error states.

## 4. Accuracy panel
Show MAE, RMSE, MBE, and WAPE, each with a one-line explanation:
- Lower MAE/RMSE = smaller errors. RMSE penalises large misses more.
- MBE > 0 = over-forecast on average. MBE < 0 = under-forecast.
- WAPE = total absolute error as a % of total actual. Show "Unavailable" when the denominator is 0.

Also show "Based on N matched intervals; X missing forecast, Y missing actual."

## 5. Interval table (`components/tables/`)
Columns: Delivery interval (local + UTC on hover) · Forecast publish time · Forecast MW · Actual MW · Error MW · |Error| MW · Status badge.
Uses server-side sorting and pagination from `/api/analysis/intervals`, right-aligned tabular numbers, and a sticky header. Clicking a row selects the interval.

## 6. Selected interval + forecast history
For the selected interval, show: delivery start, selected forecast MW, selected publish time, decision cutoff, lead time (cutoff − publish), and the eligible versions count.
A history table lists every version with an `Eligible` / `After cutoff` badge. The selected row is highlighted, and post-cutoff rows are greyed out.
Optional: a small step chart of how the forecast changed across publish times, with the cutoff drawn as a vertical line.

## 7. Data quality panel
Show the last successful fetch, API errors (if any), missing forecast and missing actual counts, coverage with its definition, the cache hit/miss status, and a prominent `LIVE` / `DEMO FIXTURE` label.

## Exit check
- [ ] Every widget shows real API values for the full month and for a single day
- [ ] Changing the cutoff visibly changes the selected publish times and metrics
- [ ] Every control does something. No console errors.
- [ ] `npm run build` passes

Stop and report, with screenshots or a description of each view.
