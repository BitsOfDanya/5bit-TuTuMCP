from datetime import date, time
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator


class TravelService(StrEnum):
    TRAIN = "train"
    FLIGHT = "flight"
    BUS = "bus"
    HOTEL = "hotel"


class TripDetails(BaseModel):
    service_type: TravelService | None = None
    origin: str | None = None
    destination: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    preferred_time: time | None = None
    passengers: int | None = Field(default=None, ge=1, le=20)
    budget: int | None = Field(default=None, ge=1)
    currency: str = Field(default="RUB", min_length=3, max_length=3)
    is_international: bool | None = None

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
    assistant_message: str = Field(
        min_length=1,
        description="Concise Markdown reply for the traveler.",
    )
    trip: TripDetails


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
        allowed = [PlanAction.NEGOTIATE_CONSTRAINTS, PlanAction.BUILD_SEARCH_REDIRECT]
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
