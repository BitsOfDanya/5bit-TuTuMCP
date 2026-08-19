from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.engine import NoMatchingTripsError
from app.schemas import BestTrip, HotelOffer, TransportOffer, TripIntent


class NegotiatorTripSpec(BaseModel):
    origin: str = Field(min_length=2, max_length=120)
    destination: str = Field(min_length=2, max_length=120)
    outbound_date: date
    return_date: date
    travelers: int = Field(default=1, ge=1, le=9)
    budget: int | None = Field(default=None, gt=0)
    max_transfers: int | None = Field(default=None, ge=0, le=5)


class NegotiatorTransportSegment(BaseModel):
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


class NegotiatorHotel(BaseModel):
    name: str
    price: int = Field(ge=0)
    rating: float | None = Field(default=None, ge=0, le=10)
    booking_url: str | None = None


class NegotiatorJourney(BaseModel):
    id: str
    total_price: int = Field(ge=0)
    transport_price: int = Field(ge=0)
    hotel_price: int = Field(ge=0)
    outbound: NegotiatorTransportSegment
    inbound: NegotiatorTransportSegment
    hotel: NegotiatorHotel | None = None


class NegotiatorAlternative(BaseModel):
    id: str
    kind: Literal["single", "combination"]
    score: float = Field(ge=0)
    new_trip_spec: NegotiatorTripSpec
    journey: NegotiatorJourney


class NegotiationResultInput(BaseModel):
    """PublicNegotiationResult contract produced by constraint-negotiator."""

    status: Literal["success", "negotiation_required", "no_options"]
    trip_spec: NegotiatorTripSpec
    journeys: list[NegotiatorJourney] = Field(default_factory=list)
    alternatives: list[NegotiatorAlternative] = Field(default_factory=list)


def adapt_negotiation_result(
    result: NegotiationResultInput,
) -> tuple[TripIntent, BestTrip]:
    trip_spec, journey = _select_journey(result)
    intent = TripIntent(
        origin=trip_spec.origin,
        destination=trip_spec.destination,
        departure_date=trip_spec.outbound_date,
        return_date=trip_spec.return_date,
        adults=trip_spec.travelers,
        budget=trip_spec.budget,
        direct_only=trip_spec.max_transfers == 0,
        hotel_rating_min=0,
    )
    return intent, _to_best_trip(journey)


def _select_journey(
    result: NegotiationResultInput,
) -> tuple[NegotiatorTripSpec, NegotiatorJourney]:
    if result.status == "success" and result.journeys:
        journey = min(result.journeys, key=lambda item: item.total_price)
        return result.trip_spec, journey

    if result.status == "negotiation_required" and result.alternatives:
        alternative = min(
            result.alternatives,
            key=lambda item: (item.score, item.journey.total_price),
        )
        return alternative.new_trip_spec, alternative.journey

    raise NoMatchingTripsError(
        "Constraint Negotiator did not return a trackable journey."
    )


def _to_best_trip(journey: NegotiatorJourney) -> BestTrip:
    useful_time_hours = max(
        0.0,
        (journey.inbound.departure - journey.outbound.arrival).total_seconds() / 3600,
    )
    transfers = journey.outbound.transfers + journey.inbound.transfers
    carriers = list(
        dict.fromkeys(
            carrier
            for carrier in (journey.outbound.carrier, journey.inbound.carrier)
            if carrier
        )
    )
    hotel = (
        HotelOffer(
            id=f"{journey.id}:hotel",
            name=journey.hotel.name,
            price_total=journey.hotel_price,
            rating=journey.hotel.rating or 0,
            checkout_url=journey.hotel.booking_url,
        )
        if journey.hotel is not None
        else None
    )
    transport = TransportOffer(
        id=f"{journey.id}:transport",
        price=journey.transport_price,
        departure_at=journey.outbound.departure,
        arrival_at=journey.outbound.arrival,
        return_departure_at=journey.inbound.departure,
        return_arrival_at=journey.inbound.arrival,
        duration_minutes=(
            _duration_minutes(journey.outbound) + _duration_minutes(journey.inbound)
        ),
        transfers=transfers,
        carriers=carriers or [journey.outbound.mode],
        search_results_url=(
            journey.outbound.booking_url or journey.inbound.booking_url
        ),
    )
    hotel_rating = hotel.rating if hotel is not None else 0
    trip_score = max(0.0, min(100.0, 80 + hotel_rating * 2 - transfers * 8))
    return BestTrip(
        total_price=journey.total_price,
        transport_price=journey.transport_price,
        hotel_price=journey.hotel_price,
        trip_score=round(trip_score, 1),
        useful_time_hours=round(useful_time_hours, 1),
        transfers=transfers,
        hotel_rating=hotel_rating,
        transport=transport,
        hotel=hotel,
    )


def _duration_minutes(segment: NegotiatorTransportSegment) -> int:
    if segment.duration_minutes is not None:
        return segment.duration_minutes
    return max(0, round((segment.arrival - segment.departure).total_seconds() / 60))
