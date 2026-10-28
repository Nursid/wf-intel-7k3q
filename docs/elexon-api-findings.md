# Elexon API Findings (Phase 1)

All findings below come from real requests made on **2026-10-28** against the public Elexon Insights API, plus its OpenAPI spec (`https://data.elexon.co.uk/swagger/v1/swagger.json`). The probe is reproducible with `py scripts/probe_elexon.py`.

## Access
- Base URL: `https://data.elexon.co.uk/bmrs/api/v1`
- Authentication: **none**. No API key is needed.
- Response format for `/stream` endpoints: a bare JSON array (no `data` wrapper, no pagination).
- Rate limits: none are documented in the spec. The client retries 429/5xx with exponential backoff anyway.

## FUELHH (actuals): `GET /datasets/FUELHH/stream`
| Param | Format | Notes |
|---|---|---|
| `settlementDateFrom` / `settlementDateTo` | `yyyy-MM-dd` | Inclusive. Cannot be combined with publish filters. |
| `publishDateTimeFrom` / `publishDateTimeTo` | ISO datetime | Alternative filter |
| `settlementPeriod` | int[] | Optional |
| `fuelType` | string[] | We send `WIND` and still filter client-side |

Record:
```json
{"dataset":"FUELHH","publishTime":"2026-01-02T00:00:00Z","startTime":"2026-01-01T23:30:00Z",
 "settlementDate":"2026-01-01","settlementPeriod":48,"fuelType":"WIND","generation":15538}
```
- Timestamps are UTC with a `Z` suffix. `generation` is an integer, in MW (30-minute average).
- `settlementDate` is the **UK local** settlement day. We fetch 2025-12-31 → 2026-02-01 and then filter on `startTime` to cover the full Europe/London month.
- Volume: 1,584 WIND rows for 2025-12-31 → 2026-02-01 (33 days × 48), with no duplicate `startTime`, no nulls and no negative values. One request took 1.6 s.

## WINDFOR (forecasts): `GET /datasets/WINDFOR/stream`
| Param | Format | Notes |
|---|---|---|
| `publishDateTimeFrom` / `publishDateTimeTo` | ISO datetime | **The only filters.** Without them the API returns only the *latest* forecast. Delivery (`startTime`) filtering is not supported. |

Record:
```json
{"dataset":"WINDFOR","publishTime":"2025-12-31T22:30:00Z","startTime":"2025-12-30T21:00:00Z","generation":6086}
```

### Important differences from the brief
1. **Forecasts are hourly.** `startTime` is always on the hour (`HH:00`), whereas the brief assumed 30-minute intervals for both datasets. FUELHH remains half-hourly.
2. **The full version history is kept.** About 8 publications a day (02:30, 04:30, 07:30, 09:30, 11:30, 15:30, 18:30, 22:30 UTC on 2025-12-31), each with 73 hourly rows. Every run published on day D covers the same window, D-1 21:00 → D+2 21:00 UTC, so the furthest a forecast reaches is about 2 days ahead.
3. Every January delivery hour we sampled has **24 forecast versions** (e.g. `2026-01-01T12:00Z`: earliest published `2025-12-30T02:30Z`). See `docs/samples/`.
4. **December 2025 publications are available.** Publications from 2025-12-25 onwards were returned, with no publication gap longer than 6 hours up to 2026-01-31.
5. Volume: 22,192 rows / 304 publications for publish window 2025-12-25 → 2026-02-01, returned in one request (2.3 s). The client still splits requests into 7-day chunks for safety.

## Design decisions that follow from this
- **Analysis grid = hourly delivery intervals** (the forecast resolution). Each hourly forecast is matched to the FUELHH actual with the **same `startTime`**, i.e. the half-hour starting on the hour, as the brief specifies. We don't interpolate forecasts to fill `:30` slots, because that would invent values.
- Coverage denominator = number of hourly delivery intervals in the selected Europe/London date range (24 per day in January).
- The chart still shows the half-hourly actuals for context.
- Forecast publications are downloaded from **2025-12-24** so that early-January deliveries have their December forecast history. Because each run only reaches about 2 days ahead, a D-2 cutoff already leaves late-evening intervals without an eligible forecast, and D-3 or earlier leaves most intervals with **none**. The app reports these as missing rather than hiding them.

## Limitations
- `generation` for WINDFOR has no documented averaging convention (hourly average vs. point value). We treat it as the MW forecast for the interval starting at `startTime`.
- The historical record is only as complete as Elexon's archive. Any missing publication shows up as reduced eligible versions or missing forecasts.
