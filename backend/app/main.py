"""FastAPI application factory."""

from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.core.config import Settings, get_settings
from app.services.analysis_service import AnalysisService
from app.services.data_repository import DataRepository
from app.services.elexon_client import ElexonError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def _warm(repository: DataRepository) -> None:
    try:
        repository.get()
    except ElexonError as exc:  # surfaced later via data_source.errors / 503
        logger.warning("Startup warm-up failed: %s", exc)


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def create_app(settings: Settings | None = None, repository: DataRepository | None = None) -> FastAPI:
    settings = settings or get_settings()
    repository = repository or DataRepository(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if settings.warm_on_startup:
            threading.Thread(target=_warm, args=(repository,), daemon=True).start()
        yield

    app = FastAPI(
        title="Wind Forecast Intelligence API",
        version=settings.app_version,
        description="Cutoff-aware analysis of Elexon national wind forecasts (WINDFOR) vs actuals (FUELHH).",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.analysis_service = AnalysisService(repository)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.exception_handler(ElexonError)
    async def _source_error(_: Request, exc: ElexonError) -> JSONResponse:
        return _error(503, "SOURCE_UNAVAILABLE", f"Elexon data is unavailable and no cache exists: {exc}")

    @app.exception_handler(HTTPException)
    async def _http_error(_: Request, exc: HTTPException) -> JSONResponse:
        code = {422: "INVALID_REQUEST", 404: "NOT_FOUND", 403: "FORBIDDEN"}.get(exc.status_code, "ERROR")
        return _error(exc.status_code, code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        msg = "; ".join(f"{'.'.join(str(p) for p in e['loc'][1:])}: {e['msg']}" for e in exc.errors())
        return _error(422, "INVALID_REQUEST", msg)

    app.include_router(router)
    return app


app = create_app()
