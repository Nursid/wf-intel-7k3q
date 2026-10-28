# Phase 10 — README, Video Script, Submission + Final Audit

## 1. README.md (repo root)
Sections, in order:
1. Overview and business problem
2. Main features (include a screenshot)
3. Architecture diagram (Mermaid): Elexon → client → cache → selector → metrics → FastAPI → React
4. Technology stack
5. Repository structure, with a one-line description per directory or file
6. Prerequisites
7. Local setup (backend + frontend, no Docker)
8. Environment variables (table: name, default, description)
9. Docker: `docker compose up --build` + URLs + health endpoint
10. API endpoints (table + example request)
11. Accuracy metric definitions + how to interpret them
12. Forecast selection and cutoff policy + **assumptions** (the default cutoff is a pilot assumption, not a market rule; publish time == cutoff counts as eligible)
13. Data source and historical limitations (real Phase 1 findings: version history, December publications, gaps)
14. Test commands + what they cover
15. Deployed app URL (verified only)
16. Backend API URL (verified only)
17. **AI tools disclosure:** state that Claude (Claude Code) was used and for what
18. Known limitations + future improvements

## 2. `docs/video-script.md` (≤ 10 min, unlisted YouTube)
**Part 1, client presentation (≤ 5 min):** the problem → dashboard tour → filters and cutoff → selected forecast and its publish time → forecast vs actual → what MAE/RMSE/MBE/WAPE mean for procurement → scope and limitations.
**Part 2, technical review (≤ 5 min):** architecture and data flow → Elexon client → cutoff selection and matching → metrics and tests (run them on screen) → code layout → Docker → deployment → assumptions.
Include timestamps, the line to say for each section, what to click, and a pre-recording checklist (warm cache, close tabs, zoom to 110%, incognito).

## 3. `docs/submission-checklist.md`
- [ ] Public GitHub repo (anonymous name) opens in incognito
- [ ] Deployed frontend opens in incognito and loads data
- [ ] Backend `/health` reachable
- [ ] Unlisted YouTube video recorded and uploaded by the user, link tested in incognito
- [ ] README links all work
- [ ] Submission form completed by the user

## 4. Final requirements audit
Go through every section of the original brief (§1–17), plus CLAUDE.md. Produce `docs/requirements-audit.md` as a table: *Requirement · Status (Done / Partial / Not done) · Evidence (file or URL) · Notes*. List anything incomplete honestly.

Stop and give the final report.
