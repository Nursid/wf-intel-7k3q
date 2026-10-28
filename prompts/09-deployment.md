# Phase 9 — Deployment

## Before you start
Confirm with the user: the backend host (from CLAUDE.md Decisions), that the CLIs are logged in, and permission to push to a **public** GitHub repo. Do not push or deploy without explicit approval.

## Tasks
1. **GitHub:**
   - Run a secret scan first (`git grep` for tokens and keys; confirm `.env` is ignored).
   - Commit, then create the public repo with the anonymous name: `gh repo create <name> --public --source . --push`.
2. **Backend** (Heroku, or the chosen alternative):
   - Heroku: `Procfile` (`web: uvicorn app.main:app --host 0.0.0.0 --port $PORT`), `.python-version` or runtime file, deploy from the `backend/` subdirectory (git subtree or container deploy).
   - Set env vars: `CORS_ORIGINS=<vercel-url>`, `DATA_MODE=live`, and the cache and cutoff defaults.
   - Ephemeral filesystem: the cache warms on first request or at startup. Document the cold-start time.
3. **Frontend (Vercel):**
   - Root directory `frontend/`. Set `VITE_API_BASE_URL=<backend-url>`. Add an SPA rewrite in `vercel.json`.
4. **Close the loop:** update the backend CORS with the final Vercel domain and redeploy.

## Verification (required before claiming success)
- [ ] `curl <backend>/health` returns 200
- [ ] `curl <backend>/api/analysis/overview` returns real data
- [ ] The deployed frontend in an **incognito** window loads every widget with no CORS or console errors
- [ ] Filters work on the deployed site

## If blocked
If a platform is unavailable (billing, verification, limits), stop. Report the exact error and propose the closest working alternative. **Do not invent URLs.**

Stop and report the verified URLs.
