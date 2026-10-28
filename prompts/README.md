# Phase-wise Build Prompts

Paste **one phase at a time** into Claude Code. Review the phase report, then move on to the next phase.
`CLAUDE.md` in the repo root holds the global rules and is loaded automatically.

| # | Phase | Output | Exit check | Est. time |
|---|-------|--------|-----------|-----------|
| 0 | [Prerequisites (you)](00-prerequisites.md) | Accounts, tools, decisions | Checklist done | 30 min |
| 1 | [Repo setup + Elexon API discovery](01-api-discovery.md) | Scaffold + `docs/elexon-api-findings.md` | Real Jan 2026 data confirmed | 1.5 h |
| 2 | [Backend data layer](02-backend-data-layer.md) | Elexon client, normalisation, cache | Client tests pass with real data | 2 h |
| 3 | [Forecast selection + metrics](03-selection-and-metrics.md) | Selector, matcher, metrics + tests | All 10 test areas pass | 2 h |
| 4 | [Backend API](04-backend-api.md) | FastAPI endpoints + schemas | `/docs` works, API tests pass | 1.5 h |
| 5 | [Frontend foundation + design system](05-frontend-foundation.md) | Layout, tokens, UI kit, API layer | App shell renders live header | 1.5 h |
| 6 | [Dashboard features](06-dashboard-features.md) | Filters, KPIs, chart, tables, quality | All widgets show real data | 3 h |
| 7 | [Integration + QA](07-integration-qa.md) | End-to-end checks, fixes | QA checklist all green | 1 h |
| 8 | [Docker](08-docker.md) | Dockerfiles, compose | `docker compose up --build` works | 45 min |
| 9 | [Deployment](09-deployment.md) | Live Vercel + backend | Deployed site verified in incognito | 1.5 h |
| 10 | [Docs, video script, submission](10-docs-video-submission.md) | README, script, checklists, audit | Requirements audit complete | 1.5 h |

**Total:** about 16 h

## How to run a phase
```
Read prompts/0N-<name>.md and execute it fully. Follow CLAUDE.md. Stop and report when done.
```
