from collections.abc import Awaitable
from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.schemas import TrackingPayload, TripTrackingResponse
from app.tracker_client import SmartTripTrackerClientDep, SmartTripTrackerError

router = APIRouter(prefix="/api/v1/tracker", tags=["smart-trip-tracker"])


@router.post("/trips", status_code=201)
async def create_tracking(
    payload: TrackingPayload,
    tracker_client: SmartTripTrackerClientDep,
) -> TripTrackingResponse:
    return await _run(tracker_client.create(payload))


@router.get("/trips/{tracking_id}")
async def get_tracking(
    tracking_id: UUID,
    tracker_client: SmartTripTrackerClientDep,
) -> TripTrackingResponse:
    return await _run(tracker_client.get(tracking_id))


@router.post("/trips/{tracking_id}/refresh")
async def refresh_tracking(
    tracking_id: UUID,
    tracker_client: SmartTripTrackerClientDep,
) -> TripTrackingResponse:
    return await _run(tracker_client.refresh(tracking_id))


@router.delete("/trips/{tracking_id}")
async def stop_tracking(
    tracking_id: UUID,
    tracker_client: SmartTripTrackerClientDep,
) -> TripTrackingResponse:
    return await _run(tracker_client.stop(tracking_id))


async def _run(operation: Awaitable[TripTrackingResponse]) -> TripTrackingResponse:
    try:
        return await operation
    except SmartTripTrackerError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
