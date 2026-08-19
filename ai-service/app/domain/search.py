from enum import StrEnum

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
