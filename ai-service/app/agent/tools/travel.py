from datetime import date, time
from typing import Any
from urllib.parse import urlencode

from langchain.tools import tool
from pydantic import BaseModel, ConfigDict, Field

from app.domain.travel import (
    AgentNextAction,
    TravelService,
    TripDetails,
    missing_trip_fields,
)


class ToolTripDetails(BaseModel):
    """Strict OpenAI tool input; unknown values are required and represented as null."""

    model_config = ConfigDict(extra="forbid")

    service_type: TravelService | None
    origin: str | None
    destination: str | None
    start_date: date | None
    end_date: date | None
    preferred_time: time | None
    passengers: int | None = Field(ge=1, le=20)
    budget: int | None = Field(ge=1)
    currency: str = Field(min_length=3, max_length=3)
    is_international: bool | None

    def to_domain(self) -> TripDetails:
        return TripDetails.model_validate(self.model_dump())


def merge_trip_details(current: TripDetails, extracted: TripDetails) -> TripDetails:
    values = current.model_dump()
    values.update(extracted.model_dump(exclude_none=True))
    if values["service_type"] is TravelService.HOTEL:
        values["origin"] = None
        values["is_international"] = None
    elif values["service_type"] is not TravelService.FLIGHT:
        values["is_international"] = None
    return TripDetails.model_validate(values)


def validate_trip(trip: TripDetails) -> dict[str, Any]:
    missing_fields = missing_trip_fields(trip)
    return {"missing_fields": missing_fields, "is_complete": not missing_fields}


def next_travel_action(trip: TripDetails) -> AgentNextAction:
    if missing_trip_fields(trip):
        return AgentNextAction.COLLECT_TRIP_DETAILS
    if trip.service_type is TravelService.FLIGHT and trip.is_international is True:
        return AgentNextAction.UPLOAD_PASSENGER_DOCUMENTS
    return AgentNextAction.REDIRECT_TO_SEARCH


def search_redirect_url(trip: TripDetails) -> str:
    missing_fields = missing_trip_fields(trip)
    if missing_fields:
        raise ValueError(f"Cannot build a redirect with missing fields: {missing_fields}")
    if trip.service_type is None:
        raise ValueError("A service type is required to build a redirect.")
    query: dict[str, str | int] = {
        "destination": trip.destination or "",
        "date": trip.start_date.isoformat() if trip.start_date else "",
        "passengers": trip.passengers or 1,
        "budget": trip.budget or 0,
        "currency": trip.currency,
    }
    if trip.origin:
        query["origin"] = trip.origin
    if trip.end_date:
        query["return_date"] = trip.end_date.isoformat()
    if trip.preferred_time:
        query["time"] = trip.preferred_time.isoformat()
    if trip.service_type is TravelService.FLIGHT:
        query["international"] = str(bool(trip.is_international)).lower()
    return f"/search/{trip.service_type.value}?{urlencode(query)}"


@tool
def validate_trip_details(trip: ToolTripDetails) -> dict[str, Any]:
    """Validate normalized trip data and return missing fields and completeness."""
    return validate_trip(trip.to_domain())


@tool
def determine_next_action(trip: ToolTripDetails) -> dict[str, str]:
    """Choose whether to collect fields, upload passenger documents, or open search."""
    return {"next_action": next_travel_action(trip.to_domain()).value}


@tool
def build_search_redirect(trip: ToolTripDetails) -> dict[str, str]:
    """Build a relative internal search URL for a complete normalized trip."""
    return {"redirect_url": search_redirect_url(trip.to_domain())}
