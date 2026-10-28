# Wind Forecast Intelligence — Project Context

This file is loaded automatically in every Claude Code session. It holds the rules that apply to **every phase**. Phase-specific instructions live in `prompts/`.

## Role
Senior Full Stack Engineer + Product Designer. Build a working, production-minded MVP — not plans, mockups, or sample code.

## Business problem
A UK energy utility buys electricity one day before delivery. For January 2026 deliveries, the procurement team needs to know:
1. Which national wind forecast was available at the decision time?
2. How accurate was it compared to actual wind generation?
3. How large were the errors, and was there a systematic over/under-estimate (bias)?

The app analyses historical forecasts. It must **not** claim to calculate optimal purchases.

## Scope (hard limits)
- Data: **only** Elexon national wind data — `FUELHH` (actuals, `fuelType == WIND`) and `WINDFOR` (forecasts).
  - FUELHH: https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream
  - WINDFOR: https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/WINDFOR/stream
- No demand, weather, price, or other generation data.
- Delivery dates: January 2026 only. Include December 2025 forecast publications that target early-January deliveries.
- Both datasets use 30-minute delivery intervals.

## Stack
- **Frontend:** React, Vite, TypeScript, Tailwind CSS, Recharts, React Router (if useful), Lucide React
- **Backend:** Python, FastAPI, Pandas, NumPy, HTTPX, Pydantic, Pytest
- **Infra:** Docker, Docker Compose, GitHub (public), Vercel (frontend), Heroku or an approved alternative (backend; see Decisions)

## Non-negotiable rules
1. **No fabrication.** Never invent API responses, metrics, market deadlines, URLs, or claim a deployment worked unless you verified it.
2. **Cutoff integrity.** A forecast published after the decision cutoff must never represent information available at decision time.
3. **No silent zero-fill.** Missing values stay missing. Leave unmatched pairs out of the metrics and report how many there were.
4. **Timezones.** All timestamps are timezone-aware. Store and compute in UTC. Display in Europe/London with a clear label. Handle daylight saving time correctly.
5. **Fixtures are labelled.** Test or demo fixtures must never be shown as real Elexon observations. The UI must say whether data is `LIVE` or `DEMO FIXTURE`.
6. **Configuration.** Settings go in environment variables. No hardcoded URLs or secrets. Never commit `.env` files.
7. **Logic stays in the backend.** The frontend handles presentation, formatting, and API state only.
8. **Read the docs first.** Verify Elexon parameters, pagination, limits, and response shape before relying on them.
9. **Every control must work.** No buttons or filters that do nothing.
10. **Phase discipline.** Finish the current phase, run its checks, then **stop and report** using the template below. Do not start the next phase until the user asks.

## Metric definitions (backend)
- error = forecast − actual
- absolute_error = |forecast − actual|
- MAE = mean(|forecast − actual|)
- RMSE = sqrt(mean((forecast − actual)²))
- MBE = mean(forecast − actual)   (positive = over-forecast, negative = under-forecast)
- WAPE = Σ|forecast − actual| / Σ|actual| × 100 → `null` when the denominator is 0
- Coverage = matched intervals ÷ expected 30-min intervals in the selected delivery range (state this denominator in the UI and README)

## Decisions
- Default decision cutoff policy: `D-1 at 09:00 Europe/London` (pilot assumption; configurable via env and per request)
- Current scope: **local only**. No GitHub, hosting or YouTube until the user asks.
- Progress: Phases 0–8 done (2026-10-28). Phase 9 (deployment) and Phase 10 (docs/video) are deliberately skipped for now.
- Docker: dashboard on :8080, API on :8000. The Windows dev machine already uses :5173 for another app.
- Backend host: undecided (Heroku / Render / Railway / Fly.io)
- GitHub repo name (anonymous, random): undecided

## Verified facts (Phases 1–5; see docs/elexon-api-findings.md)
- **WINDFOR is hourly** (startTime always HH:00), published about 8 times a day, with about 24 versions per delivery hour. FUELHH is half-hourly.
  The analysis grid is therefore **hourly**: each forecast hour is matched to the FUELHH actual with the same startTime. No interpolation.
  `/api/analysis/timeseries` returns `intervals` (hourly analysis rows) and `actuals_half_hourly` (context for the chart).
- Each WINDFOR run reaches only about 2 days ahead, so D-2 cutoffs lose some intervals and D-3 loses all. That's expected, not a bug.
- Boundary rule: publish_time == cutoff counts as eligible.
- Missing counts are inclusive (missing_forecast_count includes MISSING_BOTH).
- Dev machine: Windows Application Control blocks pandas 3.x DLLs, so pandas is pinned `<3`. Python runs through `py` / `backend/.venv`.
- Port 5173 is used by another local app on the dev machine. Use `npx vite --port 5174` and add that origin to `CORS_ORIGINS` if needed.

## Phase report template (end every phase with this)
```
## Phase N report
- Done: …
- Files changed: …
- Commands run + results (tests, builds): …
- Verified facts (with evidence): …
- Assumptions made: …
- Open issues / blockers: …
- Needed from user: …
```
