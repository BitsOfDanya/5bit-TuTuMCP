from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.engine import NoMatchingTripsError
from app.provider import DemoTripOfferProvider, TutuMcpError, TutuMcpProvider
from app.repository import SQLiteTrackingRepository, TrackingNotFoundError
from app.schemas import (
    HealthResponse,
    TrackingListResponse,
    TripIntent,
    TripTrackingResponse,
)
from app.service import InactiveTrackingError, TripTrackingService


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    trip_provider: Literal["demo", "tutu"] = "tutu"
    tutu_mcp_url: str = "https://mcp.tutu.ru/mcp"
    database_path: Path = Path(".data/smart-trip-tracker.db")


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_service() -> TripTrackingService:
    settings = get_settings()
    provider = (
        TutuMcpProvider(settings.tutu_mcp_url)
        if settings.trip_provider == "tutu"
        else DemoTripOfferProvider()
    )
    return TripTrackingService(
        provider,
        repository=SQLiteTrackingRepository(settings.database_path),
    )


ServiceDep = Annotated[TripTrackingService, Depends(get_service)]

app = FastAPI(title="Smart Trip Tracker MVP", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5174", "http://localhost:5174"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    return HealthResponse(status="ok", provider=settings.trip_provider)


@app.post("/api/v1/trips", status_code=status.HTTP_201_CREATED)
def create_tracking(intent: TripIntent, service: ServiceDep) -> TripTrackingResponse:
    return _run(lambda: service.create(intent))


@app.get("/api/v1/trips")
def list_trackings(service: ServiceDep) -> TrackingListResponse:
    return service.list()


@app.get("/api/v1/trips/{tracking_id}")
def get_tracking(tracking_id: UUID, service: ServiceDep) -> TripTrackingResponse:
    return _run(lambda: service.get(tracking_id))


@app.post("/api/v1/trips/{tracking_id}/refresh")
def refresh_tracking(tracking_id: UUID, service: ServiceDep) -> TripTrackingResponse:
    return _run(lambda: service.refresh(tracking_id))


@app.post("/api/v1/trips/{tracking_id}/simulate")
def simulate_tracking(tracking_id: UUID, service: ServiceDep) -> TripTrackingResponse:
    return _run(lambda: service.refresh(tracking_id, simulated=True))


@app.delete("/api/v1/trips/{tracking_id}")
def stop_tracking(tracking_id: UUID, service: ServiceDep) -> TripTrackingResponse:
    return _run(lambda: service.stop(tracking_id))


def _run[ResultT](operation: Callable[[], ResultT]) -> ResultT:
    try:
        return operation()
    except TrackingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InactiveTrackingError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except NoMatchingTripsError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except TutuMcpError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
