import re
from datetime import date, datetime, time
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class HealthResponse(BaseModel):
    status: str


class ReadinessResponse(BaseModel):
    status: str
    dependencies: dict[str, str]


class TravelService(StrEnum):
    TRAIN = "train"
    FLIGHT = "flight"
    BUS = "bus"
    HOTEL = "hotel"


class TripDetails(BaseModel):
    """Normalized search parameters collected from the conversation."""

    model_config = ConfigDict(extra="forbid")

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
        description=(
            "Concise Markdown reply that confirms captured data and asks for missing data."
        ),
    )
    trip: TripDetails = Field(
        description="All trip parameters known from the conversation. Unknown values stay null.",
    )


class PlanAction(StrEnum):
    EXTRACT_TRIP_DETAILS = "extract_trip_details"
    VALIDATE_TRIP_DETAILS = "validate_trip_details"
    DETERMINE_NEXT_ACTION = "determine_next_action"
    NEGOTIATE_CONSTRAINTS = "negotiate_constraints"
    BUILD_SEARCH_REDIRECT = "build_search_redirect"


class PlanStep(BaseModel):
    action: PlanAction
    reason: str = Field(min_length=1, max_length=500)


class TravelPlan(BaseModel):
    objective: str = Field(min_length=1, max_length=500)
    steps: list[PlanStep] = Field(min_length=3, max_length=5)

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
        optional = actions[3:]
        allowed = {PlanAction.NEGOTIATE_CONSTRAINTS, PlanAction.BUILD_SEARCH_REDIRECT}
        if any(action not in allowed for action in optional):
            raise ValueError("The plan contains an unsupported optional action.")
        if len(optional) != len(set(optional)):
            raise ValueError("Optional plan actions cannot be repeated.")
        if optional == [PlanAction.BUILD_SEARCH_REDIRECT, PlanAction.NEGOTIATE_CONSTRAINTS]:
            raise ValueError("Constraint negotiation must run before redirect creation.")
        return self


class AgentNextAction(StrEnum):
    COLLECT_TRIP_DETAILS = "collect_trip_details"
    UPLOAD_PASSENGER_DOCUMENTS = "upload_passenger_documents"
    REDIRECT_TO_SEARCH = "redirect_to_search"


class SearchSegment(BaseModel):
    mode: str
    origin: str
    destination: str
    departure: str
    arrival: str
    price: int = Field(ge=0)
    currency: str = "RUB"
    duration_minutes: int | None = Field(default=None, ge=0)
    transfers: int = Field(default=0, ge=0)
    carrier: str | None = None
    voyage_no: str | None = None


class SearchHotel(BaseModel):
    name: str
    price: int = Field(ge=0)
    currency: str = "RUB"
    stars: int | None = Field(default=None, ge=0, le=5)
    rating: float | None = Field(default=None, ge=0, le=10)
    address: str | None = None
    check_in: str | None = None
    check_out: str | None = None
    nights: int | None = Field(default=None, ge=1)
    photo_url: str | None = None


class TrackingTripSpec(BaseModel):
    origin: str = Field(min_length=2, max_length=120)
    destination: str = Field(min_length=2, max_length=120)
    outbound_date: date
    return_date: date
    travelers: int = Field(default=1, ge=1, le=9)
    budget: int | None = Field(default=None, gt=0)
    max_transfers: int | None = Field(default=None, ge=0, le=5)


class TrackingSegment(BaseModel):
    mode: Literal["train", "flight", "bus", "suburban_train"]
    origin: str
    destination: str
    departure: datetime
    arrival: datetime
    price: int = Field(ge=0)
    duration_minutes: int | None = Field(default=None, ge=0)
    transfers: int = Field(default=0, ge=0)
    carrier: str | None = None
    booking_url: str | None = None


class TrackingHotel(BaseModel):
    name: str
    price: int = Field(ge=0)
    rating: float | None = Field(default=None, ge=0, le=10)
    booking_url: str | None = None


class TrackingJourney(BaseModel):
    id: str
    total_price: int = Field(ge=0)
    transport_price: int = Field(ge=0)
    hotel_price: int = Field(ge=0)
    outbound: TrackingSegment
    inbound: TrackingSegment
    hotel: TrackingHotel | None = None


class TrackingPayload(BaseModel):
    status: Literal["success"] = "success"
    trip_spec: TrackingTripSpec
    journeys: list[TrackingJourney] = Field(min_length=1, max_length=1)
    alternatives: list[dict[str, object]] = Field(default_factory=list, max_length=0)


class SearchOption(BaseModel):
    id: str
    kind: Literal["journey", "relaxation"]
    title: str
    explanation: str | None = None
    total_price: int = Field(ge=0)
    currency: str = "RUB"
    outbound: SearchSegment | None = None
    inbound: SearchSegment | None = None
    hotel: SearchHotel | None = None
    changes: list[str] = Field(default_factory=list)
    action_url: str | None = None
    tracking_payload: TrackingPayload | None = None


class TrackerIntent(BaseModel):
    origin: str
    destination: str
    departure_date: date
    return_date: date
    adults: int
    budget: int | None
    direct_only: bool
    hotel_rating_min: float


class TrackerPricePoint(BaseModel):
    timestamp: datetime
    total_price: int
    trip_score: float


class TrackerTransport(BaseModel):
    id: str
    price: int
    currency: str
    departure_at: datetime
    arrival_at: datetime
    return_departure_at: datetime
    return_arrival_at: datetime
    duration_minutes: int
    transfers: int
    carriers: list[str]
    search_results_url: str | None = None


class TrackerHotel(BaseModel):
    id: str
    name: str
    price_total: int
    currency: str
    rating: float
    checkout_url: str | None = None


class TrackerBestTrip(BaseModel):
    total_price: int
    transport_price: int
    hotel_price: int
    trip_score: float
    useful_time_hours: float
    transfers: int
    hotel_rating: float
    transport: TrackerTransport
    hotel: TrackerHotel | None = None


class TrackerPriceSummary(BaseModel):
    current_price: int
    minimum_price: int
    average_price: int
    difference_from_min: int


class TrackerRecommendation(BaseModel):
    status: Literal["COLLECTING_DATA", "BUY_NOW", "WAIT", "GOOD_VALUE"]
    message: str


class TripTrackingResponse(BaseModel):
    id: UUID
    intent: TrackerIntent
    active: bool
    created_at: datetime
    last_checked_at: datetime
    summary: TrackerPriceSummary
    recommendation: TrackerRecommendation
    current_trip: TrackerBestTrip
    history: list[TrackerPricePoint]


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
    tool_statuses: dict[str, str]
    search_options: list[SearchOption] = Field(default_factory=list)
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
        field for field in required if getattr(document, field) in (None, "", PassengerSex.UNKNOWN)
    ]
    if document.document_type is IdentityDocumentType.UNKNOWN:
        missing.insert(0, "document_type")
    return list(dict.fromkeys(missing))


class AuthCodeRequest(BaseModel):
    login: str = Field(min_length=5, max_length=254)

    @field_validator("login")
    @classmethod
    def normalize_login(cls, value: str) -> str:
        return normalize_login(value)


class AuthCodeRequested(BaseModel):
    challenge_id: str
    expires_in: int
    debug_code: str | None = None


class AuthCodeVerifyRequest(BaseModel):
    challenge_id: str = Field(min_length=16, max_length=128)
    code: str = Field(pattern=r"^\d{6}$")


class PasswordAuthRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not EMAIL_PATTERN.fullmatch(normalized):
            raise ValueError("Enter a valid email address")
        return normalized


class RegisterRequest(PasswordAuthRequest):
    name: str = Field(min_length=2, max_length=80)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 2:
            raise ValueError("Enter your name")
        return normalized


class UserResponse(BaseModel):
    id: str
    login: str
    display_name: str


class AuthSessionResponse(BaseModel):
    user: UserResponse | None


class MessageResponse(BaseModel):
    message: str


def normalize_login(value: str) -> str:
    normalized = value.strip().lower()
    if "@" in normalized:
        if not EMAIL_PATTERN.fullmatch(normalized):
            raise ValueError("Enter a valid email address")
        return normalized

    digits = re.sub(r"\D", "", normalized)
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    if not 10 <= len(digits) <= 15:
        raise ValueError("Enter a valid phone number or email")
    return "+" + digits
