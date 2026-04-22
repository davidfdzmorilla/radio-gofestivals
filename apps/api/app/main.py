from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_v1_router
from app.core.config import get_settings
from app.core.db import dispose_engine, init_engine
from app.core.logging import configure_logging, get_logger
from app.core.redis import close_redis, init_redis

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

APP_VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.effective_log_level, dev=settings.is_dev)
    log = get_logger("app.lifespan")

    init_engine(settings)
    init_redis(settings)

    if settings.env != "dev":
        if not settings.gofestivals_db_url:
            log.warning(
                "gofestivals_db_url_empty",
                impact="festival links will show IDs only, not names",
            )
        if not settings.sentry_dsn:
            log.warning(
                "sentry_not_configured",
                impact="errors will only be visible in logs",
            )

    log.info("startup_complete", env=settings.env, version=APP_VERSION)

    try:
        yield
    finally:
        await dispose_engine()
        await close_redis()
        log.info("shutdown_complete")


app = FastAPI(
    title="radio.gofestivals API",
    version=APP_VERSION,
    lifespan=lifespan,
)

_settings = get_settings()
_cors_origins: list[str] = (
    ["*"] if _settings.is_dev else _settings.cors_allowed_origins
)
if not _settings.is_dev and not _settings.cors_allowed_origins:
    _cors_warning_log = get_logger("app.main")
    _cors_warning_log.warning(
        "cors_allowed_origins_empty",
        impact="cross-origin requests will be rejected outside same-origin deploy",
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_v1_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"status": "ok", "version": APP_VERSION}
