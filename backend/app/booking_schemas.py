from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas import SearchOption, TravelService


class BookingStep(StrEnum):
    SELECT_CARRIAGE = "select_carriage"
    SELECT_ROOM = "select_room"
    SELECT_FARE = "select_fare"
    SELECT_EXTRAS = "select_extras"
    SELECT_SEATS = "select_seats"
    CONFIRM_FARE = "confirm_fare"
    PASSENGERS = "passengers"
    DOCUMENTS = "documents"
    GUESTS = "guests"
    CONFIRM = "confirm"
    CHECKOUT = "checkout"


class BookingStepOption(BaseModel):
    id: str
    title: str
    description: str
    price_delta: int = 0
    available: bool = True


class CreateBookingRequest(BaseModel):
    user_id: UUID
    session_id: UUID
    option: SearchOption


class SubmitBookingStepRequest(BaseModel):
    user_id: UUID
    step: BookingStep
    data: dict[str, Any] = Field(default_factory=dict)


class BookingAssistRequest(BaseModel):
    user_id: UUID
    instruction: str = Field(default="", max_length=5_000)


class BookingAssistResponse(BaseModel):
    assistant_message: str
    proposed_data: dict[str, Any] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    can_apply: bool = False
    requires_user_confirmation: bool = True


class BookingResponse(BaseModel):
    id: UUID
    user_id: UUID
    session_id: UUID
    product_type: TravelService
    option: SearchOption
    steps: list[BookingStep]
    current_step: BookingStep
    completed_steps: list[BookingStep]
    selections: dict[str, Any]
    travelers_count: int
    current_options: list[BookingStepOption]
    checkout_url: str | None = None
    inventory_source: Literal["preview"] = "preview"
    provider_notice: str = (
        "Наличие и цена окончательно подтверждаются на стороне Туту перед оплатой."
    )
