import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.booking.graph import get_booking_copilot
from app.domain.booking import BookingCopilotRequest, BookingCopilotResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["booking"])
BookingCopilotDep = Annotated[Any, Depends(get_booking_copilot)]


@router.post("/booking/assist")
async def assist_booking(
    request: BookingCopilotRequest,
    copilot: BookingCopilotDep,
) -> BookingCopilotResponse:
    try:
        result = await copilot.ainvoke({"request": request})
        return BookingCopilotResponse.model_validate(result["response"])
    except Exception as exc:
        logger.exception("Booking copilot invocation failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The booking copilot could not produce a response.",
        ) from exc
