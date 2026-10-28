# Phase 8 — Docker

## Goal
Make the app start locally with one command: `docker compose up --build`.

## Tasks
1. **`backend/Dockerfile`:** python:3.11-slim, non-root user, `pip install --no-cache-dir`, uvicorn on `$PORT` (default 8000), `HEALTHCHECK` hitting `/health`.
2. **`frontend/Dockerfile`:** multi-stage build. Node 20 builds the app, then nginx serves `dist/` with an SPA fallback. `VITE_API_BASE_URL` is a build arg.
3. **`.dockerignore`** for both (exclude `node_modules`, `.venv`, caches, `.env`, tests where appropriate).
4. **`docker-compose.yml`:**
   - `backend` on port 8000 with a healthcheck and a named volume for `CACHE_DIR`
   - `frontend` on port 5173 (or 8080), `depends_on: backend: condition: service_healthy`
   - Environment from `.env` with defaults. Update `.env.example` with every variable and a comment for each.
5. Make sure the browser-side frontend can reach the backend (`VITE_API_BASE_URL=http://localhost:8000`) and that CORS allows the frontend origin.

## Exit check
- [ ] A clean `docker compose up --build` starts both services, and both report healthy
- [ ] Frontend URL, backend URL, and `/health` all verified
- [ ] The dashboard loads real data inside the containers
- [ ] The cache survives a container restart

Stop and report, including the exact URLs.
