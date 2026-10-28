# Phase 1 — Repo Setup + Elexon API Discovery

## Goal
Set up the repository and **prove with real requests** that the Elexon APIs can supply January 2026 data. Write no application logic yet.

## Tasks
1. **Inspect** the repo. Report what exists and keep any good conventions.
2. **Scaffold** the monorepo:
   ```
   backend/   frontend/   docs/   prompts/   CLAUDE.md   .gitignore   .env.example
   ```
   Run `git init`. Add a `.gitignore` covering Python, Node, `.env*` (but not `.env.example`), caches, `dist/`, and `node_modules/`.
3. **Read the official docs** for `FUELHH/stream` and `WINDFOR/stream`. Record:
   - Base URL, path, and HTTP method
   - Query parameters (names, formats, required or optional, max range)
   - Pagination behaviour, if any
   - Authentication (expected: none)
   - Rate limits and response size limits
   - Response JSON shape (exact field names and types)
4. **Probe the live API** with small real requests (curl or a throwaway script in `scripts/`). Check:
   - FUELHH returns `WIND` rows for 1–31 Jan 2026 at 30-minute intervals.
   - WINDFOR returns forecasts targeting January 2026, including **publishTimes in December 2025** for early-January deliveries.
   - Whether WINDFOR keeps **multiple forecast versions** per `startTime` (count the distinct `publishTime` values per interval).
   - How many records a full month returns, and whether the request has to be split into chunks.
   - What timezone the timestamps use (UTC `Z`?).
5. **Save small real samples** to `docs/samples/` (a few records each, clearly named `*.sample.json`) for reference.

## Deliverable
`docs/elexon-api-findings.md` containing: endpoints, parameters, response schema, pagination and chunking strategy, version history findings, record counts, gaps found, and limitations. Every claim must be backed by a real request.

## Exit check
- [ ] Real FUELHH WIND data confirmed for January 2026
- [ ] Real WINDFOR data confirmed, with multiple publishTimes per interval (or the limitation documented)
- [ ] December 2025 publications for early-January targets confirmed or ruled out
- [ ] If the data is unavailable, **stop** and report the blocker. Do not build on guesses.

Stop and report using the template in CLAUDE.md.
