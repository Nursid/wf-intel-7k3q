# Phase 4 — Backend API

## Goal
Expose the analysis through a small, coherent, typed FastAPI API.

## Files
```
backend/app/api/routes.py
backend/app/schemas/analysis.py
backend/app/services/analysis_service.py   # orchestrates cache → select → match → metrics
backend/tests/test_api.py
```

## Shared query parameters
| Param | Type | Default | Rule |
|---|---|---|---|
| `start_date` | date (Europe/London) | 2026-01-01 | Must fall within January 2026 |
| `end_date` | date (Europe/London) | 2026-01-31 | Must be ≥ start_date and in January 2026 |
| `cutoff_mode` | `relative` \| `absolute` | `relative` | |
| `cutoff_day_offset` | int | config | 0–7 |
| `cutoff_time` | `HH:MM` (Europe/London) | config | |
| `decision_at` | ISO datetime with offset | – | Required when `cutoff_mode=absolute` |

Invalid input returns **422** with a clear message.

## Endpoints
| Method | Path | Returns |
|---|---|---|
| GET | `/health` | `{status, version, data_source, cache_fetched_at}` |
| GET | `/api/meta` | Available date range, default cutoff policy, data source (`LIVE`/`DEMO FIXTURE`), last successful fetch, last error |
| GET | `/api/analysis/overview` | KPI totals + metrics + coverage + data-quality block |
| GET | `/api/analysis/timeseries` | Per-interval `{start_utc, forecast_mw, actual_mw, error_mw}` for the chart |
| GET | `/api/analysis/intervals` | Paginated + sortable interval table (`page`, `page_size`, `sort_by`, `sort_dir`) with publish time and status |
| GET | `/api/analysis/forecast-history` | For `?start_time=<utc>`: all forecast versions, eligible/ineligible flags, selected version, cutoff, lead time |
| POST | `/api/admin/refresh` | Forces a cache refresh (guard it with an env token, or disable it in prod) |

Every response includes a `data_source` block: `{mode: "LIVE" | "DEMO FIXTURE", fetched_at_utc, cache_hit, errors[]}`.
Timestamps are returned as ISO 8601 UTC (`Z`). The frontend converts them for display.

## Behaviour
- If Elexon is down and no cache exists, return **503** with a structured error body.
- CORS: allow the origins listed in `CORS_ORIGINS` only.
- Avoid recomputing for identical queries. An LRU cache keyed by the parameters is enough.

## Tests (`test_api.py`, using a fixture-backed app)
Cover the happy path for every endpoint, validation errors (dates outside January, end before start, absolute mode without `decision_at`), a 503 when the source fails, schema conformance, pagination and sorting, and a check that forecast-history never marks a post-cutoff version as selected.

## Exit check
- [ ] `pytest` all green
- [ ] `uvicorn app.main:app` runs, and `/docs` shows every endpoint
- [ ] Real responses checked with curl. Paste a short excerpt of `/api/analysis/overview`.

Stop and report.
