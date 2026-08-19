from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import (
    CORSMiddleware,
)

from app.api.preferences import (
    router as preferences_router,
)
from app.api.routes import (
    router as rescue_router,
)
from app.api.system import (
    router as system_router,
)
from app.api.whatif import (
    router as whatif_router,
)
from app.config import (
    get_settings,
)
from app.middleware.runtime import (
    RateLimitMiddleware,
    RequestObservabilityMiddleware,
)


logging.basicConfig(
    level=os.getenv(
        "LOG_LEVEL",
        "INFO",
    ).upper(),
    format=(
        "%(asctime)s "
        "%(levelname)s "
        "%(name)s "
        "%(message)s"
    ),
)


settings = get_settings()


app = FastAPI(
    title="Trip Rescue",
    description=(
        "Minimal intelligent travel replan "
        "and decision simulation service "
        "powered by Tutu MCP."
    ),
    version="0.2.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=(
        settings.cors_origins_list
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.add_middleware(
    RateLimitMiddleware
)


app.add_middleware(
    RequestObservabilityMiddleware
)


app.include_router(
    rescue_router
)

app.include_router(
    whatif_router
)

app.include_router(
    preferences_router
)

app.include_router(
    system_router
)


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": "trip-rescue",
        "version": "0.2.0",
    }


@app.get("/ready")
async def ready() -> dict:
    return {
        "status": "ready",
    }