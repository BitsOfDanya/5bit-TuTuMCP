from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.trip import TransportMode


class TransportSegment(BaseModel):
    id: str

    mode: TransportMode

    origin: str
    destination: str

    departure: datetime
    arrival: datetime

    price: int = Field(ge=0)

    source_price: float | None = Field(
        default=None,
        ge=0,
    )

    currency: str = "RUB"

    duration_minutes: int | None = Field(
        default=None,
        ge=0,
    )

    transfers: int = Field(
        default=0,
        ge=0,
    )

    carrier: str | None = None
    voyage_no: str | None = None

    booking_url: str | None = None
    search_results_url: str | None = None

    checkout_ref: dict[str, Any] | None = None
    details_ref: dict[str, Any] | None = None

    rating: float | None = None
    review_count: int | None = None


class HotelOption(BaseModel):
    id: str

    name: str

    price: int = Field(
        ge=0
    )

    source_price: float | None = Field(
        default=None,
        ge=0,
    )

    currency: str = "RUB"

    stars: int | None = Field(
        default=None,
        ge=0,
        le=5,
    )

    rating: float | None = Field(
        default=None,
        ge=0,
        le=10,
    )

    review_count: int | None = Field(
        default=None,
        ge=0,
    )

    address: str | None = None

    room_name: str | None = None
    room_size_sqm: float | None = None

    check_in: date | None = None
    check_out: date | None = None

    nights: int | None = Field(
        default=None,
        ge=1,
    )

    breakfast_included: bool | None = None
    meal_name: str | None = None

    free_cancellation: bool | None = None

    booking_url: str | None = None

    checkout_ref: dict[str, Any] | None = None

    offerpack_hash: str | None = None

    photo_url: str | None = None


class JourneyOption(BaseModel):
    id: str

    outbound: TransportSegment
    inbound: TransportSegment

    hotel: HotelOption | None = None

    total_price: int = Field(
        ge=0
    )

    @property
    def transport_modes(
        self,
    ) -> set[TransportMode]:
        return {
            self.outbound.mode,
            self.inbound.mode,
        }

    @property
    def max_transfers(self) -> int:
        return max(
            self.outbound.transfers,
            self.inbound.transfers,
        )

    @property
    def transport_price(self) -> int:
        return (
            self.outbound.price
            + self.inbound.price
        )

    @property
    def hotel_price(self) -> int:
        if self.hotel is None:
            return 0

        return self.hotel.price