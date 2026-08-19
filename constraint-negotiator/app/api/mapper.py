from __future__ import annotations

from app.api.schemas import (
    PublicHotelOption,
    PublicJourneyOption,
    PublicNegotiationResult,
    PublicRelaxationPlan,
    PublicTransportSegment,
)
from app.models.journey import (
    HotelOption,
    JourneyOption,
    TransportSegment,
)
from app.models.relaxation import (
    NegotiationResult,
)


def to_public_result(
    result: NegotiationResult,
) -> PublicNegotiationResult:

    return PublicNegotiationResult(
        status=result.status,
        trip_spec=result.trip_spec,
        journeys=[
            _to_public_journey(
                journey
            )
            for journey
            in result.journeys
        ],
        alternatives=[
            _to_public_alternative(
                alternative
            )
            for alternative
            in result.alternatives
            if alternative.summary is not None
        ],
    )


def _to_public_alternative(
    alternative,
) -> PublicRelaxationPlan:

    if alternative.summary is None:
        raise ValueError(
            "RelaxationPlan summary "
            "is required for public API"
        )

    return PublicRelaxationPlan(
        id=alternative.id,
        kind=alternative.kind,
        changes=alternative.changes,
        score=alternative.score,
        new_trip_spec=(
            alternative.new_trip_spec
        ),
        summary=alternative.summary,
        journey=(
            _to_public_journey(
                alternative.journey
            )
        ),
    )


def _to_public_journey(
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
        destination=segment.destination,
        departure=segment.departure,
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