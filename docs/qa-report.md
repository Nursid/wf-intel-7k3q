# QA Report (Phase 7)

Date: 2026-10-28 · Data: live Elexon download (312 WINDFOR publications, 1,584 FUELHH WIND half-hours)

## Correctness: independent recomputation
`scripts/qa_verify.py` reimplements cutoff selection and every metric using only the Python standard library (no app code, no pandas). It reads the raw cache and compares the results with the running API. Full output: [qa-verify-output.txt](qa-verify-output.txt).

| Check | Scenarios | Result |
|---|---|---|
| MAE, RMSE, MBE, WAPE, matched and expected counts equal the independent values (to 1e-6) | D-1 09:00, D-0 07:00, D-2 09:00 (full month); D-1 16:00 (week 1); D-3 09:00 (15 Jan, 0 % coverage) | ✅ |
| Every interval's selected publish time and value equal the independent selection | 744 + 744 + 744 + 168 + 24 intervals | ✅ 0 mismatches |
| No selected forecast published after its cutoff | All of the above | ✅ 0 violations |
| Spot checks via `/forecast-history`, including an early-January hour selected from a **December 2025** publication | 1 Jan 06:00Z → 31 Dec 07:30Z (11 of 24 versions eligible), plus 3 random hours | ✅ |
| Same checks against the Docker stack | — | ✅ |

Automated regression tests: **83 backend tests** (pytest; this includes an invariant scan over the real-data fixture) and **11 frontend tests** (vitest: London/UTC conversion, DST day lengths, URL filter round-trip, validation, formatting).

## UX checks (headless Chrome screenshots)
| Check | Result |
|---|---|
| Full month, week, single day and 2-day ranges render real values | ✅ |
| Changing the cutoff changes selected publish times and metrics (D-1 09:00 MAE 2,127 MW → D-0 07:00 MAE 726 MW on 15–16 Jan) | ✅ |
| D-3 cutoff: KPIs show "—" (not 0), coverage 0 % with a Gaps badge, and missing counts are disclosed | ✅ |
| Fixed-time mode: one decision time for all hours; hours beyond the forecast horizon are reported as missing | ✅ |
| Backend stopped: header shows "Unavailable", page shows an error with Retry | ✅ |
| Filters are kept in the URL (shareable); Reset restores defaults; Apply is disabled while the draft is invalid or unchanged | ✅ |
| Selecting a chart point or table row updates the selected-interval panel and the chart marker | ✅ |
| Layout at 1440, 1024 and 768 px with no horizontal page scroll | ✅ |
| Browser console: no errors or warnings | ✅ |
| Keyboard: filters are labelled form controls; table rows can be focused and selected with Enter/Space; sortable headers are buttons with `aria-sort`; focus rings visible | ✅ (code review) |
| Chart colours validated for colour-vision deficiency (blue/green ΔE 24.9; amber/violet ΔE 34.6); the forecast line is also dashed | ✅ |

## Performance (warm cache, measured on 127.0.0.1)
| Endpoint | Time |
|---|---|
| overview (full month) | 4 ms |
| timeseries (full month, 744 + 1,488 points) | 85 ms |
| intervals (500 rows) | 39 ms |
| overview with a new cutoff (cache miss) | 6 ms |

A cold start downloads from Elexon in about 5 s. On Windows, `localhost` from Python tries IPv6 first and adds about 2 s, so the QA script uses `127.0.0.1`.

## Fixes made during QA
- Interval table: unit labels rendered before column names, the Status column was clipped, and blank space appeared under the rows. Fixed.
- History chart: ticks ignored the post-cutoff series. Fixed with explicit ticks.
- The decision-day dropdown truncated its labels. Shortened the labels and widened the column.
- The fixed-time cutoff description showed a raw ISO string. Now reads "Fixed decision time 2026-01-04 09:00 UTC".
- The production bundle exceeded 500 kB. Split into app (61 kB), react and chart chunks.

## Known limitations
- Forecasts are hourly while actuals are half-hourly. Accuracy is measured on hourly intervals (documented in the UI).
- January contains no DST change, so DST handling is covered by unit tests rather than real data.
