from fastapi import FastAPI

from app.api import router as agent_router
from app.schemas import HealthResponse

app = FastAPI(
    title="TuTuMCP Agent API",
    version="0.1.0",
)
app.include_router(agent_router)


@app.get("/health")
def health() -> HealthResponse:
    return HealthResponse(status="ok")
