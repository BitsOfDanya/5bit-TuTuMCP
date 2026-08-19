from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import router as agent_router
from app.database import dispose_database
from app.schemas import HealthResponse


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await dispose_database()


app = FastAPI(
    title="TuTuMCP Agent API",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(agent_router)


@app.get("/health")
def health() -> HealthResponse:
    return HealthResponse(status="ok")
