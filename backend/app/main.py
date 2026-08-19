from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, status

from app.ai_client import AIServiceClientDep, AIServiceError
from app.api import router as agent_router
from app.auth_api import router as auth_router
from app.database import dispose_database
from app.db import create_db_and_tables
from app.schemas import HealthResponse, ReadinessResponse
from app.tracker_api import router as tracker_router

FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    create_db_and_tables()
    yield
    await dispose_database()


app = FastAPI(
    title="TuTuMCP API",
    version="0.2.0",
    lifespan=lifespan,
)
app.include_router(agent_router)
app.include_router(auth_router)
app.include_router(tracker_router)


@app.get("/health")
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/ready")
async def ready(ai_client: AIServiceClientDep) -> ReadinessResponse:
    try:
        ai_health = await ai_client.health()
    except AIServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return ReadinessResponse(
        status="ready",
        dependencies={"ai-service": ai_health["status"]},
    )


if FRONTEND_DIST.is_dir():
    app.frontend("/", directory=FRONTEND_DIST)
