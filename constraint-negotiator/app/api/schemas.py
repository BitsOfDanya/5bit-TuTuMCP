from __future__ import annotations

from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, Field

from app.models.relaxation import (
    ConstraintChange,
    RelaxationSummary,
)
from app.models.trip import (
    TransportMode,
    TripSpec,
)


class PublicTransportSegment(BaseModel):
    mode: TransportMode

    origin: str
    destination: str

    departure: datetime
    arrival: datetime

    price: int = Field(
        ge=0
    )

    duration_minutes: int | None = None
    transfers: int = 0

    carrier: str | None = None
    voyage_no: str | None = None

    rating: float | None = None
    review_count: int | None = None

    booking_url: str | None = None


class PublicHotelOption(BaseModel):
    name: str

    price: int = Field(
        ge=0
    )

    stars: int | None = None
    rating: float | None = None
    review_count: int | None = None

    address: str | None = None
    room_name: str | None = None

    check_in: date | None = None
    check_out: date | None = None
    nights: int | None = None

    booking_url: str | None = None
    photo_url: str | None = None


class PublicJourneyOption(BaseModel):
    id: str

    total_price: int = Field(
        ge=0
    )

    transport_price: int = Field(
        ge=0
    )

    hotel_price: int = Field(
        ge=0
    )

    outbound: PublicTransportSegment
    inbound: PublicTransportSegment

    hotel: PublicHotelOption | None = None


class PublicRelaxationPlan(BaseModel):
    id: str

    kind: Literal[
        "single",
        "combination",
    ]

    changes: list[
        ConstraintChange
    ]

    score: float

    new_trip_spec: TripSpec

    summary: RelaxationSummary

    journey: PublicJourneyOption


class PublicNegotiationResult(BaseModel):
    status: Literal[
        "success",
        "negotiation_required",
        "no_options",
    ]

    trip_spec: TripSpec

    journeys: list[
        PublicJourneyOption
    ] = Field(
        default_factory=list
    )

    alternatives: list[
        PublicRelaxationPlan
    ] = Field(
        default_factory=list
    )


class ProductSearchRequest(BaseModel):
    service_type: Literal["train", "flight", "bus", "hotel"]
    destination: str = Field(min_length=2)
    start_date: date
    travelers: int = Field(default=1, ge=1, le=9)
    origin: str | None = Field(default=None, min_length=2)
    end_date: date | None = None
    preferred_time: time | None = None
    budget: int | None = Field(default=None, gt=0)


class PublicProductSearchOption(BaseModel):
    id: str
    kind: Literal["journey"] = "journey"
    title: str
    total_price: int = Field(ge=0)
    currency: str = "RUB"
    outbound: PublicTransportSegment | None = None
    inbound: PublicTransportSegment | None = None
    hotel: PublicHotelOption | None = None
    changes: list[str] = Field(default_factory=list)
    action_url: str | None = None


class PublicProductSearchResult(BaseModel):
    status: Literal["success", "no_options", "unavailable"]
    options: list[PublicProductSearchOption] = Field(default_factory=list)
