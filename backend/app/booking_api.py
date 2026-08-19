from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_client import AIServiceClientDep, AIServiceError
from app.booking_schemas import (
    BookingAssistRequest,
    BookingAssistResponse,
    BookingResponse,
    CreateBookingRequest,
    SubmitBookingStepRequest,
)
from app.bookings import BookingNotFoundError, BookingService, BookingValidationError
from app.conversations import ConversationRepository
from app.database import get_db_session
from app.schemas import TripDetails

router = APIRouter(prefix="/api/v1/bookings", tags=["bookings"])
DatabaseSessionDep = Annotated[AsyncSession, Depends(get_db_session)]


@router.post("")
async def create_booking(
    request: CreateBookingRequest,
    database_session: DatabaseSessionDep,
) -> BookingResponse:
    try:
        return await BookingService(database_session).create(request)
    except BookingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Диалог не найден."
        ) from exc
    except BookingValidationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/{booking_id}")
async def get_booking(
    booking_id: UUID,
    user_id: Annotated[UUID, Query()],
    database_session: DatabaseSessionDep,
) -> BookingResponse:
    try:
        return await BookingService(database_session).get(booking_id, user_id)
    except BookingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Оформление не найдено."
        ) from exc


@router.post("/{booking_id}/steps")
async def submit_booking_step(
    booking_id: UUID,
    request: SubmitBookingStepRequest,
    database_session: DatabaseSessionDep,
) -> BookingResponse:
    try:
        return await BookingService(database_session).submit(booking_id, request)
    except BookingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Оформление не найдено."
        ) from exc
    except BookingValidationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/{booking_id}/assist")
async def assist_booking(
    booking_id: UUID,
    request: BookingAssistRequest,
    ai_client: AIServiceClientDep,
    database_session: DatabaseSessionDep,
) -> BookingAssistResponse:
    service = BookingService(database_session)
    try:
        booking = await service.get(booking_id, request.user_id)
    except BookingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Оформление не найдено."
        ) from exc

    stored = await ConversationRepository(database_session).load(
        request.user_id,
        booking.session_id,
    )
    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Диалог не найден."
        )
    conversation, messages = stored
    try:
        result = await ai_client.assist_booking(
            {
                "product_type": booking.product_type.value,
                "current_step": booking.current_step.value,
                "travelers_count": booking.travelers_count,
                "current_options": [
                    option.model_dump(mode="json") for option in booking.current_options
                ],
                "selections": booking.selections,
                "trip": TripDetails.model_validate(conversation.trip).model_dump(mode="json"),
                "conversation": [f"{message.role}: {message.content}" for message in messages],
                "instruction": request.instruction,
            }
        )
    except AIServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Джарвелл не смог подготовить этот шаг. Попробуйте ещё раз.",
        ) from exc

    proposed_data = service.sanitize_assistance(booking, result.proposed_data)
    return BookingAssistResponse(
        assistant_message=result.assistant_message,
        proposed_data=proposed_data,
        missing_fields=result.missing_fields,
        can_apply=bool(proposed_data),
        requires_user_confirmation=True,
    )
