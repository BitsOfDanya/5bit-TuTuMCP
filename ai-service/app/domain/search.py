from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class SearchOptionKind(StrEnum):
    JOURNEY = "journey"
    RELAXATION = "relaxation"


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
    booking_url: str | None = None


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
    booking_url: str | None = None


class TrackingTripSpec(BaseModel):
    origin: str
    destination: str
    outbound_date: str
    return_date: str
    travelers: int = Field(default=1, ge=1, le=9)
    budget: int | None = Field(default=None, gt=0)
    max_transfers: int | None = Field(default=None, ge=0, le=5)


class TrackingSegment(BaseModel):
    mode: Literal["train", "flight", "bus", "suburban_train"]
    origin: str
    destination: str
    departure: str
    arrival: str
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
    kind: SearchOptionKind
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
