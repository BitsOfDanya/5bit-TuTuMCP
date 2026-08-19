from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import (
    CORSMiddleware,
)

from app.api.routes import (
    router as negotiator_router,
)
from app.api.system import (
    router as system_router,
)
from app.config import get_settings


settings = get_settings()


app = FastAPI(
    title="Constraint Negotiator",
    description=(
        "Constraint-aware travel negotiation "
        "service powered by Tutu MCP."
    ),
    version="0.1.0",
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


app.include_router(
    negotiator_router
)

app.include_router(
    system_router
)


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": (
            "constraint-negotiator"
        ),
    }


@app.get("/ready")
async def ready() -> dict:
    """
    Lightweight deployment readiness probe.

    Does NOT call external services.
    """
    return {
        "status": "ready",
    }