from __future__ import annotations

from datetime import date, datetime
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