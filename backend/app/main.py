from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.api import router as agent_router
from app.auth_api import router as auth_router
from app.database import dispose_database
from app.db import create_db_and_tables
from app.schemas import HealthResponse

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


@app.get("/health")
def health() -> HealthResponse:
    return HealthResponse(status="ok")


if FRONTEND_DIST.is_dir():
    app.frontend("/", directory=FRONTEND_DIST)
