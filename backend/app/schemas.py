from datetime import date, datetime, time
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class HealthResponse(BaseModel):
    status: str


class TravelService(StrEnum):
    TRAIN = "train"
    FLIGHT = "flight"
    BUS = "bus"
    HOTEL = "hotel"


class TripDetails(BaseModel):
    """Normalized search parameters collected from the conversation."""

    service_type: TravelService | None = Field(
        default=None,
        description="Requested service: train, flight, bus, or hotel.",
    )
    origin: str | None = Field(
        default=None,
        description="Departure city or station. Not required for a hotel search.",
    )
    destination: str | None = Field(
        default=None,
        description="Arrival city, station, airport, or hotel destination.",
    )
    start_date: date | None = Field(
        default=None,
        description="Departure or hotel check-in date in ISO 8601 format.",
    )
    end_date: date | None = Field(
        default=None,
        description="Return or hotel check-out date in ISO 8601 format.",
    )
    preferred_time: time | None = Field(
        default=None,
        description="Preferred departure time. Optional for hotels.",
    )
    passengers: int | None = Field(
        default=None,
        ge=1,
        le=20,
        description="Total number of passengers or hotel guests.",
    )
    budget: int | None = Field(
        default=None,
        ge=1,
        description="Maximum total budget in the selected currency.",
    )
    currency: str = Field(
        default="RUB",
        min_length=3,
        max_length=3,
        description="ISO 4217 currency code. Use RUB when unspecified.",
    )
    is_international: bool | None = Field(
        default=None,
        description="Whether a flight crosses a national border. Only applicable to flights.",
    )

    @field_validator("origin", "destination")
    @classmethod
    def normalize_location(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class AgentTurn(BaseModel):
    """Structured response produced by the travel intake executor."""

    assistant_message: str = Field(
        min_length=1,
        description="Concise reply that confirms captured data and asks for missing data.",
    )
    trip: TripDetails = Field(
        description="All trip parameters known from the conversation. Unknown values stay null.",
    )


class PlanAction(StrEnum):
    EXTRACT_TRIP_DETAILS = "extract_trip_details"
    VALIDATE_TRIP_DETAILS = "validate_trip_details"
    DETERMINE_NEXT_ACTION = "determine_next_action"
    BUILD_SEARCH_REDIRECT = "build_search_redirect"


class PlanStep(BaseModel):
    action: PlanAction
    reason: str = Field(min_length=1, max_length=500)


class TravelPlan(BaseModel):
    objective: str = Field(min_length=1, max_length=500)
    steps: list[PlanStep] = Field(min_length=3, max_length=4)

    @model_validator(mode="after")
    def validate_step_order(self) -> "TravelPlan":
        actions = [step.action for step in self.steps]
        required_prefix = [
            PlanAction.EXTRACT_TRIP_DETAILS,
            PlanAction.VALIDATE_TRIP_DETAILS,
            PlanAction.DETERMINE_NEXT_ACTION,
        ]
        if actions[:3] != required_prefix:
            raise ValueError("The plan must start with extract, validate, and next action.")
        if len(actions) == 4 and actions[3] is not PlanAction.BUILD_SEARCH_REDIRECT:
            raise ValueError("The optional fourth step must build the search redirect.")
        return self


class AgentNextAction(StrEnum):
    COLLECT_TRIP_DETAILS = "collect_trip_details"
    UPLOAD_PASSENGER_DOCUMENTS = "upload_passenger_documents"
    REDIRECT_TO_SEARCH = "redirect_to_search"


class AgentRequest(BaseModel):
    user_id: UUID
    session_id: UUID | None = None
    message: str = Field(min_length=1, max_length=20_000)


class AgentResponse(BaseModel):
    user_id: UUID
    session_id: UUID
    response: str
    trip: TripDetails
    missing_fields: list[str]
    is_complete: bool
    next_action: AgentNextAction
    plan: TravelPlan
    tools_used: list[str]
    redirect_url: str | None = None


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


class ConversationHistoryResponse(BaseModel):
    user_id: UUID
    session_id: UUID
    messages: list[ChatMessage]
    trip: TripDetails
    missing_fields: list[str]
    is_complete: bool
    next_action: AgentNextAction
    redirect_url: str | None = None


class ConversationSummary(BaseModel):
    session_id: UUID
    trip: TripDetails
    message_count: int
    created_at: datetime
    updated_at: datetime


class UserConversationsResponse(BaseModel):
    user_id: UUID
    sessions: list[ConversationSummary]


class IdentityDocumentType(StrEnum):
    INTERNATIONAL_PASSPORT = "international_passport"
    DOMESTIC_PASSPORT = "domestic_passport"
    BIRTH_CERTIFICATE = "birth_certificate"
    UNKNOWN = "unknown"


class PassengerSex(StrEnum):
    MALE = "male"
    FEMALE = "female"
    UNKNOWN = "unknown"


class PassengerDocumentData(BaseModel):
    """Fields read from one passenger identity document."""

    document_type: IdentityDocumentType
    last_name: str | None = None
    first_name: str | None = None
    middle_name: str | None = None
    last_name_latin: str | None = None
    first_name_latin: str | None = None
    date_of_birth: date | None = None
    sex: PassengerSex
    citizenship: str | None = None
    document_series: str | None = None
    document_number: str | None = None
    issue_date: date | None = None
    expiration_date: date | None = None
    issuing_country: str | None = None
    issued_by: str | None = None
    place_of_birth: str | None = None
    warnings: list[str] = Field(default_factory=list)

    @field_validator(
        "last_name",
        "first_name",
        "middle_name",
        "last_name_latin",
        "first_name_latin",
        "citizenship",
        "document_series",
        "document_number",
        "issuing_country",
        "issued_by",
        "place_of_birth",
    )
    @classmethod
    def normalize_document_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class PassengerDocumentExtractionResponse(BaseModel):
    user_id: UUID
    session_id: UUID
    media_type: Literal["image/png", "image/jpeg", "application/pdf"]
    document: PassengerDocumentData
    missing_fields: list[str]
    manual_review_required: bool
    redirect_url: str | None = None


def missing_trip_fields(trip: TripDetails) -> list[str]:
    if trip.service_type is None:
        return ["service_type"]

    required = ["destination", "start_date", "passengers", "budget"]
    if trip.service_type is TravelService.HOTEL:
        required.append("end_date")
    else:
        required.extend(["origin", "preferred_time"])
        if trip.service_type is TravelService.FLIGHT:
            required.append("is_international")

    return [field for field in required if getattr(trip, field) is None]


def missing_document_fields(document: PassengerDocumentData) -> list[str]:
    required = [
        "last_name",
        "first_name",
        "date_of_birth",
        "sex",
        "citizenship",
        "document_number",
    ]
    if document.document_type is IdentityDocumentType.INTERNATIONAL_PASSPORT:
        required.extend(
            [
                "last_name_latin",
                "first_name_latin",
                "expiration_date",
                "issuing_country",
            ]
        )
    elif document.document_type in {
        IdentityDocumentType.DOMESTIC_PASSPORT,
        IdentityDocumentType.BIRTH_CERTIFICATE,
    }:
        required.append("document_series")

    missing = [
        field
        for field in required
        if getattr(document, field) in (None, "", PassengerSex.UNKNOWN)
    ]
    if document.document_type is IdentityDocumentType.UNKNOWN:
        missing.insert(0, "document_type")
    return list(dict.fromkeys(missing))
