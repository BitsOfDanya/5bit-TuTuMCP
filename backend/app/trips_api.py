import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth_dependencies import CurrentUserDep
from app.database import get_db_session
from app.itineraries import AcceptedItineraryRepository
from app.schemas import (
    AcceptedItineraryResponse,
    AcceptItineraryRequest,
    DecisionServiceResponse,
    DecisionTextRequest,
)
from app.trip_rescue_client import TripRescueClientDep, TripRescueError

router = APIRouter(prefix="/api/v1/trips/current", tags=["current-trip"])
logger = logging.getLogger(__name__)
DatabaseSessionDep = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("", response_model=AcceptedItineraryResponse)
async def get_current_itinerary(
    user: CurrentUserDep,
    database_session: DatabaseSessionDep,
) -> AcceptedItineraryResponse:
    record = await AcceptedItineraryRepository(database_session).get(user.id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Принятая поездка не найдена.",
        )
    return AcceptedItineraryResponse(
        trip=record.trip_spec,
        journey=record.journey,
        updated_at=record.updated_at,
    )


@router.put("", response_model=AcceptedItineraryResponse)
async def accept_itinerary(
    request: AcceptItineraryRequest,
    user: CurrentUserDep,
    database_session: DatabaseSessionDep,
    trip_rescue: TripRescueClientDep,
) -> AcceptedItineraryResponse:
    record = await AcceptedItineraryRepository(database_session).save(
        user_id=user.id,
        trip_spec=request.trip.model_dump(mode="json"),
        journey=request.journey.model_dump(mode="json"),
    )
    try:
        await trip_rescue.record_preference_feedback(
            profile_id=user.id,
            candidate=request.journey.model_dump(mode="json"),
        )
    except TripRescueError:
        logger.warning(
            "Accepted itinerary was saved, but preference feedback failed",
            exc_info=True,
        )
    return AcceptedItineraryResponse(
        trip=record.trip_spec,
        journey=record.journey,
        updated_at=record.updated_at,
    )


@router.post("/rescue", response_model=DecisionServiceResponse)
async def rescue_current_itinerary(
    request: DecisionTextRequest,
    user: CurrentUserDep,
    database_session: DatabaseSessionDep,
    trip_rescue: TripRescueClientDep,
) -> DecisionServiceResponse:
    record = await _require_itinerary(database_session, user.id)
    try:
        result = await trip_rescue.rescue_from_text(
            trip=record.trip_spec,
            journey=record.journey,
            message=request.message,
            profile_id=user.id,
        )
    except TripRescueError as exc:
        raise _http_error(exc) from exc
    return DecisionServiceResponse(kind="rescue", result=result)


@router.post("/what-if", response_model=DecisionServiceResponse)
async def simulate_current_itinerary(
    request: DecisionTextRequest,
    user: CurrentUserDep,
    database_session: DatabaseSessionDep,
    trip_rescue: TripRescueClientDep,
) -> DecisionServiceResponse:
    record = await _require_itinerary(database_session, user.id)
    try:
        result = await trip_rescue.what_if_from_text(
            trip=record.trip_spec,
            journey=record.journey,
            message=request.message,
            profile_id=user.id,
        )
    except TripRescueError as exc:
        raise _http_error(exc) from exc
    return DecisionServiceResponse(kind="what_if", result=result)


async def _require_itinerary(database_session: AsyncSession, user_id: str):
    record = await AcceptedItineraryRepository(database_session).get(user_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Сначала примите вариант поездки.",
        )
    return record


def _http_error(exc: TripRescueError) -> HTTPException:
    status_code = exc.status_code if 400 <= exc.status_code < 500 else 502
    return HTTPException(status_code=status_code, detail=exc.detail)
