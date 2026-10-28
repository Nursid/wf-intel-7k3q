# Phase 2 — Backend Data Layer

## Goal
Build a robust Elexon client that fetches, validates, normalises, and caches January 2026 data. Base it on the findings in `docs/elexon-api-findings.md`.

## Structure
```
backend/
  app/
    main.py                  # minimal FastAPI app + /health for now
    core/config.py           # pydantic-settings: env vars
    services/elexon_client.py
    services/normalize.py    # raw → typed DataFrames
    services/cache.py
  tests/
  requirements.txt
  pytest.ini
```

## Tasks
1. **Config** (`core/config.py`, env-driven): `ELEXON_BASE_URL`, `HTTP_TIMEOUT_S`, `HTTP_MAX_RETRIES`, `CACHE_DIR`, `CACHE_TTL_HOURS`, `DATA_MODE` (`live` | `fixture`), `CORS_ORIGINS`, `DEFAULT_CUTOFF_TIME`, `DEFAULT_CUTOFF_DAY_OFFSET`.
2. **Elexon client** (HTTPX):
   - Fetch FUELHH (filtered to `WIND`) and WINDFOR for a date range, split into chunks according to the Phase 1 findings.
   - Fetch WINDFOR publications from **late December 2025** onwards so early-January targets have their history.
   - Use timeouts, retries with backoff on 429/5xx, and clear typed exceptions (`ElexonUnavailableError`, `ElexonResponseError`).
   - Validate responses with Pydantic. Skip malformed rows and **count** them. Never crash on a single bad record.
3. **Normalisation:**
   - Actuals → `start_time_utc`, `actual_mw`
   - Forecasts → `start_time_utc`, `publish_time_utc`, `forecast_mw`
   - Parse every timestamp as tz-aware UTC. Remove exact duplicates. Reject non-numeric or NaN generation values (count them, don't zero them).
4. **Cache:**
   - Store the normalised January 2026 dataset (Parquet or JSON) in `CACHE_DIR`, with metadata: `fetched_at_utc`, `source` (`elexon-live` or `fixture`), row counts, and errors.
   - January 2026 is historical, so the cache can be long-lived. Allow a forced refresh.
   - If the live fetch fails but a cache exists, serve the cache and report it as stale or cached. Never pretend it's fresh.
5. **Fixture mode:** generate a small, clearly labelled demo fixture from real samples, for offline dev only. It is tagged `source = "fixture"` everywhere.

## Tests (`tests/test_elexon_client.py`)
Mock HTTP with `respx` or similar. Cover chunking, retries, timeouts, 5xx and 429 responses, malformed JSON, missing fields, non-WIND rows filtered out, and timezone parsing.
Add one optional live smoke test marked `@pytest.mark.live`, skipped by default.

## Exit check
- [ ] `pytest` passes
- [ ] A real fetch of all of January 2026 is cached. Report row counts and the time taken.
- [ ] A second load is served from cache, with no network calls

Stop and report.
