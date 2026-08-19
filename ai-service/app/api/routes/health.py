from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import ConstraintNegotiatorDep, SmartTripTrackerDep
from app.api.schemas import ReadinessResponse
from app.integrations.constraint_negotiator.client import ConstraintNegotiatorUnavailable
from app.integrations.smart_trip_tracker.client import SmartTripTrackerUnavailable

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "jarvell-ai"}


@router.get("/ready")
async def ready(
    negotiator: ConstraintNegotiatorDep,
    tracker: SmartTripTrackerDep,
) -> ReadinessResponse:
    try:
        negotiator_health = await negotiator.health()
        tracker_health = await tracker.health()
    except (ConstraintNegotiatorUnavailable, SmartTripTrackerUnavailable) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return ReadinessResponse(
        status="ready",
        dependencies={
            "constraint-negotiator": negotiator_health["status"],
            "smart-trip-tracker": tracker_health["status"],
        },
    )
