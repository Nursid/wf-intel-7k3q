# Wind Forecast Intelligence

Cutoff-aware analysis of UK national wind generation forecasts (Elexon **WINDFOR**) against actual generation (Elexon **FUELHH**, fuel type WIND) for January 2026 deliveries.

It answers three procurement questions:
1. Which forecast was available at the decision time?
2. How accurate was it?
3. Did forecasts systematically over- or under-estimate?

It does **not** recommend purchase volumes.

> Status: Phases 0–8 complete and running locally (data, logic, API, dashboard, QA, Docker). Deployment and the demo video are intentionally not done yet.

## Quick start (Docker)
```bash
docker compose up --build
```
| | URL |
|---|---|
| Dashboard | http://localhost:8080 |
| API | http://localhost:8000 · docs at `/docs` · health at `/health` |

- The backend downloads January 2026 data from Elexon at startup (about 5 s, internet required) and keeps it in the `elexon-cache` volume across restarts.
- Ports can be changed with `FRONTEND_PORT` / `BACKEND_PORT`. If you change the dashboard port, also set `CORS_ORIGINS`.
- Stop with `docker compose down`. Add `-v` to also delete the cached data.

## Run without Docker
**Backend** (Python 3.11+; tested on 3.12 in Docker and 3.14 on Windows)
```bash
cd backend
py -m venv .venv                                  # python3 -m venv .venv on macOS/Linux
.venv/Scripts/python -m pip install -r requirements-dev.txt
.venv/Scripts/python -m uvicorn app.main:app --port 8000
```
**Frontend** (Node 20.19+ or 22+)
```bash
cd frontend
npm install
npm run dev                                       # http://localhost:5173
```
If 5173 is taken, use `npx vite --port 5174` and start the backend with `CORS_ORIGINS=http://localhost:5174`.
Offline: set `DATA_MODE=fixture` to use the bundled **DEMO FIXTURE** (1–3 Jan only). It is clearly labelled in the UI.

## Using the dashboard
- **Filters:** delivery date range (January 2026; quick ranges for the month and each week) and the **decision cutoff**, either:
  - *Day-ahead rule*: D-0 to D-3 at a chosen time, Europe/London; or
  - *Fixed time*: one decision moment for every hour.

  Click **Apply**. **Reset filters** restores the defaults. Filters are stored in the URL, so a view can be shared by link.
- **KPI cards:** mean selected forecast, mean actual, MAE, bias (over/under badge), coverage.
- **Chart:** dashed blue is the selected forecast (hourly) and solid green is actual (30-min). Tick **Show error bars** to see over/under per hour. Click the chart to inspect an hour.
- **Accuracy metrics:** MAE, RMSE, MBE and WAPE, each explained, with the number of hours used and the number missing.
- **Interval table:** sortable and paginated. Click a row to inspect it.
- **Selected interval:** the forecast used, when it was published, the cutoff, lead time, eligible versions, and a chart plus table of every forecast version (eligible vs after cutoff).
- **Data quality:** live vs fixture label, last fetch, cache state, API errors, missing counts, coverage definition, ingest validation counts, assumptions.

## API
| Endpoint | Purpose |
|---|---|
| `GET /health` | Liveness + whether the dataset is loaded |
| `GET /api/meta` | Available range, default cutoff, dataset stats, data source, assumptions |
| `GET /api/analysis/overview` | MAE, RMSE, MBE, WAPE, coverage, missing counts |
| `GET /api/analysis/timeseries` | Hourly forecast/actual/error rows + half-hourly actuals |
| `GET /api/analysis/intervals` | Paginated, sortable interval table (`page`, `page_size`, `sort_by`, `sort_dir`) |
| `GET /api/analysis/forecast-history?start_time=` | All forecast versions for one hour, with eligible/selected flags |
| `POST /api/admin/refresh` | Re-download from Elexon (needs `ADMIN_TOKEN` + `X-Admin-Token` header) |

Common parameters: `start_date`, `end_date` (Europe/London days), `cutoff_mode=relative|absolute`, `cutoff_day_offset` (0–7), `cutoff_time=HH:MM`, `decision_at` (ISO with offset). Errors return `{"error": {"code", "message"}}`: 422 for bad input, 503 if Elexon is down and there is no cache.

## Method
- **Selection:** for each delivery hour, the latest forecast published **at or before** the cutoff. Later forecasts are never used and there is no fallback.
- **Default cutoff:** D-1 09:00 Europe/London. This is a configurable **pilot assumption**, not a market rule.
- **Matching:** WINDFOR is **hourly** (verified), so each forecast hour is matched to the FUELHH actual with the same `startTime`. There is no interpolation.
- **Metrics** (matched hours only; missing values are never zero-filled):
  - error = forecast − actual
  - MAE = mean |error|
  - RMSE = √mean(error²)
  - MBE = mean error (positive = over-forecast)
  - WAPE = Σ|error| / Σ|actual| × 100, or unavailable if the denominator is 0
- **Coverage** = matched hours ÷ expected hours in the selected Europe/London period.
- Source details and limitations: [docs/elexon-api-findings.md](docs/elexon-api-findings.md).

## Tests
```bash
cd backend && .venv/Scripts/python -m pytest          # 83 tests, no network
cd backend && .venv/Scripts/python -m pytest -m live  # optional live Elexon smoke test
cd frontend && npm test && npm run lint && npm run build
backend/.venv/Scripts/python scripts/qa_verify.py     # independent recomputation vs the running API
```
Results: [docs/qa-report.md](docs/qa-report.md).

## Repository layout
```
backend/   FastAPI app: api/ (routes), services/ (Elexon client, normalisation, cache, selector, metrics), schemas/, tests/
frontend/  React + Vite + Tailwind + Recharts dashboard: components/, pages/, hooks/, services/api.ts, lib/
scripts/   probe_elexon.py (API findings), build_demo_fixture.py, qa_verify.py
docs/      API findings, QA report, samples
prompts/   phase-by-phase build prompts
```

## AI disclosure
Built with the help of Claude (Anthropic) via Claude Code.
