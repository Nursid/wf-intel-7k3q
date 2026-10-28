# Wind Forecast Intelligence

Cutoff-aware analysis of UK national wind generation forecasts (Elexon **WINDFOR**) against actual generation (Elexon **FUELHH**, fuel type WIND) for January 2026 deliveries.

It answers three procurement questions:
1. Which forecast was available at the decision time?
2. How accurate was it?
3. Did forecasts systematically over- or under-estimate?

It does **not** recommend purchase volumes.

## Live demo
| | URL |
|---|---|
| **Dashboard** | https://wf-intel-7k3q-1.onrender.com |
| **Backend API** | https://wf-intel-7k3q.onrender.com (docs: [/docs](https://wf-intel-7k3q.onrender.com/docs), health: [/health](https://wf-intel-7k3q.onrender.com/health)) |
| Example | [Week 2, D-1 09:00 cutoff](https://wf-intel-7k3q-1.onrender.com/?from=2026-01-08&to=2026-01-14) |

Hosted on Render's free plan: after about 15 minutes idle, the first request takes 30–60 s while the backend wakes up and re-downloads the January data from Elexon.

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
- **Filters:** **decision dates** (purchase decisions in January 2026; quick ranges for the month and each week), which delivery day the purchase is for (next day = day-ahead, the default; same day; 2 or 3 days later), and the decision time (Europe/London). The delivery days covered are shown underneath; for example, January day-ahead decisions cover **2 Jan – 1 Feb**.

  Click **Apply**. **Reset filters** restores the defaults. Filters are stored in the URL, so a view can be shared by link.
- **KPI cards:** mean selected forecast, mean actual, MAE, bias (over/under badge), coverage.
- **Chart:** dashed blue is the selected forecast (hourly), solid green is actual (30-min), and the shaded band is the **80% range** where actual landed relative to the forecast. Tick **Error bars** to see over/under per hour. Click the chart to inspect an hour.
- **Error range:** a planning view of the error, e.g. *"In 80% of hours, actual wind was between 4,154 MW below and 426 MW above the forecast"*. It includes 50/80/90% ranges, the share of hours within ±0.5/1/2/3 GW, and a histogram of forecast − actual.
- **Accuracy metrics:** MAE, RMSE, MBE and WAPE, each explained, with the number of hours used and the number missing.
- **Interval table:** sortable and paginated. Click a row to inspect it.
- **Selected interval:** the forecast used, when it was published, the cutoff, lead time, eligible versions, and a chart plus table of every forecast version. Each version is marked eligible, *after cutoff*, or *after hour began*.
- **Data quality:** live vs fixture label, last fetch, cache state, API errors, missing counts, coverage definition, ingest validation counts, assumptions.

## API
| Endpoint | Purpose |
|---|---|
| `GET /health` | Liveness + whether the dataset is loaded |
| `GET /api/meta` | Available range, default cutoff, dataset stats, data source, assumptions |
| `GET /api/analysis/overview` | MAE, RMSE, MBE, WAPE, coverage, missing counts, **error distribution** (percentiles, 50/80/90% ranges, within-±X shares, histogram) |
| `GET /api/analysis/timeseries` | Hourly forecast/actual/error rows with the 80% range + half-hourly actuals |
| `GET /api/analysis/intervals` | Paginated, sortable interval table (`page`, `page_size`, `sort_by`, `sort_dir`) |
| `GET /api/analysis/forecast-history?start_time=` | All forecast versions for one hour, with eligible/selected flags |
| `POST /api/admin/refresh` | Re-download from Elexon (needs `ADMIN_TOKEN` + `X-Admin-Token` header) |

Common parameters: `decision_start_date`, `decision_end_date` (Europe/London days, within January 2026), `cutoff_day_offset` (0–3; 1 = day-ahead), `cutoff_time=HH:MM`. The response's `period` reports both the decision dates and the delivery dates they cover. Errors return `{"error": {"code", "message"}}`: 422 for bad input, 503 if Elexon is down and there is no cache.

## Method
- **Scope:** *purchase decisions made in January 2026* (from the brief). Delivery day = decision day + offset, so the day-ahead default covers deliveries on **2 Jan – 1 Feb 2026**.
- **Selection:** for each delivery hour, the latest forecast published **at or before the cutoff and at or before the start of that hour**. Later versions are never used and there is no fallback. The second condition matters for same-day decisions: WINDFOR runs also contain hours that have already started, and those values are observations rather than forecasts.
- **Default cutoff:** D-1 09:00 Europe/London. This is a configurable **pilot assumption**, not a market rule. Confirm it against the auction the team uses.
- **Matching:** WINDFOR is **hourly** (verified), so each forecast hour is matched to the FUELHH actual with the same `startTime`. There is no interpolation.
- **Metrics** (matched hours only; missing values are never zero-filled):
  - error = forecast − actual
  - MAE = mean |error|
  - RMSE = √mean(error²)
  - MBE = mean error (positive = over-forecast)
  - WAPE = Σ|error| / Σ|actual| × 100, or unavailable if the denominator is 0
- **Error range:** empirical percentiles of forecast − actual over the matched hours. Since actual = forecast − error, the 80% range for actual is [forecast − P90, forecast − P10], floored at 0 MW. It is in-sample and describes past performance; it is not a probabilistic forecast.
- **Coverage** = matched hours ÷ expected hours on the delivery days covered by the selected decision dates.
- Source details and limitations: [docs/elexon-api-findings.md](docs/elexon-api-findings.md).

## Tests
```bash
cd backend && .venv/Scripts/python -m pytest          # 92 tests, no network
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
