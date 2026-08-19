from __future__ import annotations

from typing import Literal

from pydantic import (
    BaseModel,
    Field,
)

from app.api.schemas import (
    PublicHotelOption,
    PublicJourneyOption,
    PublicTransportSegment,
)
from app.models.journey import (
    HotelOption,
    JourneyOption,
    TransportSegment,
)
from app.models.rescue import (
    RescueComponent,
    TripField,
)
from app.models.trip import (
    TripSpec,
)
from app.whatif.models import (
    WhatIfCandidate,
    WhatIfImpact,
    WhatIfResult,
    WhatIfStatus,
)


class PublicWhatIfImpact(
    BaseModel
):
    price_delta: int

    savings: int = Field(
        ge=0
    )

    price_change_percent: (
        float
        | None
    ) = None

    outbound_departure_delta_minutes: int

    inbound_arrival_delta_minutes: int

    components_changed: list[
        RescueComponent
    ] = Field(
        default_factory=list
    )

    components_preserved: list[
        RescueComponent
    ] = Field(
        default_factory=list
    )

    disruption_count: int = Field(
        ge=0
    )


class PublicWhatIfCandidate(
    BaseModel
):
    id: str

    rank: int = Field(
        ge=1
    )

    journey: PublicJourneyOption

    impact: PublicWhatIfImpact


class PublicWhatIfResponse(
    BaseModel
):
    """
    Frontend-safe What-if response.

    A What-if response is always simulation-only.
    Nothing here means that a trip was committed.
    """

    simulation: Literal[True] = True

    status: WhatIfStatus

    hypothetical_trip: TripSpec

    changed_fields: list[
        TripField
    ] = Field(
        default_factory=list
    )

    baseline_valid: bool

    baseline_journey: (
        PublicJourneyOption
    )

    candidates: list[
        PublicWhatIfCandidate
    ] = Field(
        default_factory=list
    )


def to_public_whatif_response(
    result: WhatIfResult,
) -> PublicWhatIfResponse:
    return PublicWhatIfResponse(
        status=result.status,
        hypothetical_trip=(
            result.hypothetical_trip
        ),
        changed_fields=list(
            result.changed_fields
        ),
        baseline_valid=(
            result.baseline_valid
        ),
        baseline_journey=(
            to_public_journey(
                result.baseline_journey
            )
        ),
        candidates=[
            to_public_whatif_candidate(
                candidate
            )
            for candidate
            in result.candidates
        ],
    )


def to_public_whatif_candidate(
    candidate: WhatIfCandidate,
) -> PublicWhatIfCandidate:
    return PublicWhatIfCandidate(
        id=candidate.id,
        rank=candidate.rank,
        journey=(
            to_public_journey(
                candidate.journey
            )
        ),
        impact=(
            to_public_whatif_impact(
                candidate.impact
            )
        ),
    )


def to_public_whatif_impact(
    impact: WhatIfImpact,
) -> PublicWhatIfImpact:
    return PublicWhatIfImpact(
        price_delta=(
            impact.price_delta
        ),
        savings=impact.savings,
        price_change_percent=(
            impact.price_change_percent
        ),
        outbound_departure_delta_minutes=(
            impact
            .outbound_departure_delta_minutes
        ),
        inbound_arrival_delta_minutes=(
            impact
            .inbound_arrival_delta_minutes
        ),
        components_changed=list(
            impact.components_changed
        ),
        components_preserved=list(
            impact.components_preserved
        ),
        disruption_count=(
            impact.disruption_count
        ),
    )


def to_public_journey(
    journey: JourneyOption,
) -> PublicJourneyOption:
    return PublicJourneyOption(
        id=journey.id,
        total_price=(
            journey.total_price
        ),
        transport_price=(
            journey.transport_price
        ),
        hotel_price=(
            journey.hotel_price
        ),
        outbound=(
            _to_public_segment(
                journey.outbound
            )
        ),
        inbound=(
            _to_public_segment(
                journey.inbound
            )
        ),
        hotel=(
            _to_public_hotel(
                journey.hotel
            )
            if journey.hotel
            is not None
            else None
        ),
    )


def _to_public_segment(
    segment: TransportSegment,
) -> PublicTransportSegment:
    return PublicTransportSegment(
        mode=segment.mode,
        origin=segment.origin,
        destination=(
            segment.destination
        ),
        departure=(
            segment.departure
        ),
        arrival=segment.arrival,
        price=segment.price,
        duration_minutes=(
            segment.duration_minutes
        ),
        transfers=segment.transfers,
        carrier=segment.carrier,
        voyage_no=segment.voyage_no,
        rating=segment.rating,
        review_count=(
            segment.review_count
        ),
        booking_url=(
            segment.booking_url
        ),
    )


def _to_public_hotel(
    hotel: HotelOption,
) -> PublicHotelOption:
    return PublicHotelOption(
        name=hotel.name,
        price=hotel.price,
        stars=hotel.stars,
        rating=hotel.rating,
        review_count=(
            hotel.review_count
        ),
        address=hotel.address,
        room_name=hotel.room_name,
        check_in=hotel.check_in,
        check_out=hotel.check_out,
        nights=hotel.nights,
        booking_url=(
            hotel.booking_url
        ),
        photo_url=hotel.photo_url,
    )