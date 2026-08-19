from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.domain.travel import TripDetails


class BookingProductType(StrEnum):
    TRAIN = "train"
    FLIGHT = "flight"
    BUS = "bus"
    HOTEL = "hotel"


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


class BookingOption(BaseModel):
    id: str
    title: str
    description: str
    price_delta: int = 0
    available: bool = True


class BookingTravelerDraft(BaseModel):
    full_name: str | None = None
    birth_date: str | None = None
    document_type: Literal[
        "international_passport",
        "domestic_passport",
        "birth_certificate",
    ] | None = None
    document_number: str | None = None


class BookingCopilotDecision(BaseModel):
    assistant_message: str = Field(min_length=1, max_length=2_000)
    option_id: str | None = Field(
        default=None,
        description="Exact available option id for a single-choice step.",
    )
    option_ids: list[str] = Field(
        default_factory=list,
        description="Exact available option ids for the select_extras step.",
    )
    seat_ids: list[str] = Field(
        default_factory=list,
        description="Exact available seat ids, one per traveler, for select_seats.",
    )
    travelers: list[BookingTravelerDraft] = Field(
        default_factory=list,
        description="Passenger or guest drafts copied only from explicit user-provided facts.",
    )
    missing_fields: list[str] = Field(
        default_factory=list,
        description="Fields that are still unknown and must be provided by the user.",
    )


class BookingCopilotRequest(BaseModel):
    product_type: BookingProductType
    current_step: BookingStep
    travelers_count: int = Field(ge=1, le=20)
    current_options: list[BookingOption] = Field(default_factory=list)
    selections: dict[str, Any] = Field(default_factory=dict)
    trip: TripDetails
    conversation: list[str] = Field(default_factory=list, max_length=200)
    instruction: str = Field(default="", max_length=5_000)


class BookingCopilotResponse(BaseModel):
    assistant_message: str
    proposed_data: dict[str, Any] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    can_apply: bool = False
    requires_user_confirmation: bool = True
