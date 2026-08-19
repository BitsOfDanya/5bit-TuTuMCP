from fastapi import FastAPI

from app.api.router import api_router
from app.api.routes.health import router as health_router


def create_app() -> FastAPI:
    application = FastAPI(
        title="Jarvell AI Service",
        description="Stateless LangGraph and document extraction service for TuTuMCP.",
        version="0.1.0",
    )
    application.include_router(health_router)
    application.include_router(api_router)
    return application


app = create_app()
