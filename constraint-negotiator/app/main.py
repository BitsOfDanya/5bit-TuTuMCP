from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as negotiator_router
from app.config import get_settings


settings = get_settings()

app = FastAPI(
    title="5BIT Constraint Negotiator",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    negotiator_router
)


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": "constraint-negotiator",
    }