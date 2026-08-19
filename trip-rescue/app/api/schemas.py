from __future__ import annotations

from datetime import (
    date,
    datetime,
)
from typing import (
    Any,
    Literal,
)

from pydantic import (
    BaseModel,
    Field,
)

from app.models.rescue import (
    RescueComponent,
    RescueExecutionResult,
    RescuePlanningResult,
    RescueValidation,
    TripDiff,
    TripField,
)
from app.models.trip import (
    ConstraintField,
    TransportMode,
    TripSpec,
)


class CurrentTransportInput(BaseModel):
    id: str | None = None

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


class CurrentHotelInput(BaseModel):
    id: str | None = None

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


class CurrentJourneyInput(BaseModel):
    id: str

    total_price: int = Field(
        ge=0
    )

    outbound: CurrentTransportInput
    inbound: CurrentTransportInput

    hotel: CurrentHotelInput | None = None


class PublicTransportSegment(BaseModel):
    mode: TransportMode

    origin: str
    destination: str

    departure: datetime
    arrival: datetime

    price: int

    duration_minutes: int | None = None
    transfers: int = 0

    carrier: str | None = None
    voyage_no: str | None = None

    rating: float | None = None
    review_count: int | None = None

    booking_url: str | None = None


class PublicHotelOption(BaseModel):
    name: str
    price: int

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

    total_price: int
    transport_price: int
    hotel_price: int

    outbound: PublicTransportSegment
    inbound: PublicTransportSegment

    hotel: PublicHotelOption | None = None


class PublicRescueInsight(BaseModel):
    type: Literal[
        "hotel_unused_nights"
    ]

    severity: Literal[
        "info",
        "warning",
    ]

    title: str
    description: str

    component: (
        RescueComponent
        | None
    ) = None

    action: Literal[
        "search_shorter_hotel"
    ] | None = None

    estimated_amount: (
        int
        | None
    ) = None

    estimated_unused_nights: (
        int
        | None
    ) = None


class PublicRescueRelaxation(BaseModel):
    field: ConstraintField

    title: str
    description: str

    old_value: Any = None
    new_value: Any = None

    magnitude: float
    score: float


class RescueCandidateSummary(BaseModel):
    headline: str
    explanation: str

    price_delta_label: str

    previous_total_price: int
    new_total_price: int


class PublicRescueCandidate(BaseModel):
    id: str

    replaced_components: list[
        RescueComponent
    ]

    preserved_components: list[
        RescueComponent
    ]

    score: float

    exact: bool = True

    relaxations: list[
        PublicRescueRelaxation
    ] = Field(
        default_factory=list
    )

    suggested_trip: (
        TripSpec
        | None
    ) = None

    summary: (
        RescueCandidateSummary
    )

    insights: list[
        PublicRescueInsight
    ] = Field(
        default_factory=list
    )

    journey: PublicJourneyOption


class RawRescueResponse(BaseModel):
    status: Literal[
        "no_change",
        "candidates_found",
        "negotiation_required",
        "no_candidates",
    ]

    previous_trip: TripSpec
    updated_trip: TripSpec

    diff: TripDiff

    validation: RescueValidation

    planning: RescuePlanningResult

    execution: RescueExecutionResult


class PublicRescueResponse(BaseModel):
    status: Literal[
        "no_change",
        "candidates_found",
        "negotiation_required",
        "no_candidates",
    ]

    updated_trip: TripSpec

    changed_fields: list[
        TripField
    ]

    preserved_components: list[
        RescueComponent
    ]

    replace_components: list[
        RescueComponent
    ]

    reasons: list[str] = Field(
        default_factory=list
    )

    candidates: list[
        PublicRescueCandidate
    ] = Field(
        default_factory=list
    )