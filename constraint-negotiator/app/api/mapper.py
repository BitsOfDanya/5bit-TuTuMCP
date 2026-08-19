from __future__ import annotations

import asyncio
from typing import Any

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
from app.tutu.client import TutuMCPClient


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


async def attach_checkout_links(
    public: PublicNegotiationResult,
    result: NegotiationResult,
    client: TutuMCPClient | None = None,
) -> PublicNegotiationResult:
    """Resolve opaque Tutu checkout refs without exposing them to the frontend."""
    tutu = client or TutuMCPClient()
    journeys = {journey.id: journey for journey in result.journeys}
    journeys.update(
        {
            plan.journey.id: plan.journey
            for plan in result.alternatives
            if plan.summary is not None
        }
    )
    public_journeys = [*public.journeys, *(plan.journey for plan in public.alternatives)]
    await asyncio.gather(
        *(
            _attach_journey_checkout(public_journey, journeys[public_journey.id], tutu)
            for public_journey in public_journeys
            if public_journey.id in journeys
        )
    )
    return public


async def _attach_journey_checkout(
    public: PublicJourneyOption,
    journey: JourneyOption,
    client: TutuMCPClient,
) -> None:
    outbound_url, inbound_url, hotel_url = await asyncio.gather(
        _checkout_url(
            client,
            journey.outbound.checkout_ref,
            journey.outbound.booking_url or journey.outbound.search_results_url,
        ),
        _checkout_url(
            client,
            journey.inbound.checkout_ref,
            journey.inbound.booking_url or journey.inbound.search_results_url,
        ),
        _checkout_url(
            client,
            journey.hotel.checkout_ref if journey.hotel else None,
            journey.hotel.booking_url if journey.hotel else None,
        ),
    )
    public.outbound.booking_url = outbound_url
    public.inbound.booking_url = inbound_url
    if public.hotel is not None:
        public.hotel.booking_url = hotel_url


async def _checkout_url(
    client: TutuMCPClient,
    checkout_ref: dict[str, Any] | None,
    fallback: str | None,
) -> str | None:
    if checkout_ref:
        try:
            payload = await client.call_tool(
                name="create_checkout_link",
                arguments=checkout_ref,
            )
        except RuntimeError:
            payload = {}
        for key in ("checkout_url", "deeplink", "url", "search_results_url"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return fallback


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
