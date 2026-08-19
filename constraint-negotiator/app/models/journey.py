from __future__ import annotations

from datetime import datetime

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
    transfers: int = Field(default=0, ge=0)

    booking_url: str | None = None


class HotelOption(BaseModel):
    id: str

    name: str
    price: int = Field(ge=0)

    rating: float | None = Field(
        default=None,
        ge=0,
        le=10,
    )


class JourneyOption(BaseModel):
    id: str

    outbound: TransportSegment
    inbound: TransportSegment

    hotel: HotelOption | None = None

    total_price: int = Field(ge=0)

    @property
    def transport_modes(self) -> set[TransportMode]:
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