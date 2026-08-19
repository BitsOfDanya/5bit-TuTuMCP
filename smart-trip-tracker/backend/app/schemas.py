from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class TripIntent(BaseModel):
    origin: str = Field(min_length=2, max_length=120)
    destination: str = Field(min_length=2, max_length=120)
    departure_date: date
    return_date: date
    adults: int = Field(default=1, ge=1, le=6)
    budget: int | None = Field(default=None, ge=1)
    direct_only: bool = False
    hotel_rating_min: float = Field(default=0, ge=0, le=10)

    @model_validator(mode="after")
    def validate_dates_and_route(self) -> "TripIntent":
        if self.return_date <= self.departure_date:
            raise ValueError("Return date must be after departure date.")
        if self.origin.strip().casefold() == self.destination.strip().casefold():
            raise ValueError("Origin and destination must be different.")
        self.origin = self.origin.strip()
        self.destination = self.destination.strip()
        return self


class TransportOffer(BaseModel):
    id: str
    price: int = Field(ge=0)
    currency: str = "RUB"
    departure_at: datetime
    arrival_at: datetime
    return_departure_at: datetime
    return_arrival_at: datetime
    duration_minutes: int = Field(ge=0)
    transfers: int = Field(ge=0)
    carriers: list[str] = Field(default_factory=list)
    search_results_url: str | None = None


class HotelOffer(BaseModel):
    id: str
    name: str
    price_total: int = Field(ge=0)
    currency: str = "RUB"
    rating: float = Field(ge=0, le=10)
    checkout_url: str | None = None


class TripCandidates(BaseModel):
    transport: list[TransportOffer]
    hotels: list[HotelOffer]


class BestTrip(BaseModel):
    total_price: int
    transport_price: int
    hotel_price: int
    trip_score: float
    useful_time_hours: float
    transfers: int
    hotel_rating: float
    transport: TransportOffer
    hotel: HotelOffer


class RecommendationStatus(StrEnum):
    COLLECTING_DATA = "COLLECTING_DATA"
    BUY_NOW = "BUY_NOW"
    WAIT = "WAIT"
    GOOD_VALUE = "GOOD_VALUE"


class PricePoint(BaseModel):
    timestamp: datetime
    total_price: int
    trip_score: float


class TripSnapshot(BaseModel):
    id: UUID
    tracking_id: UUID
    timestamp: datetime
    best_trip: BestTrip
    simulated: bool = False


class PriceSummary(BaseModel):
    current_price: int
    minimum_price: int
    average_price: int
    difference_from_min: int


class Recommendation(BaseModel):
    status: RecommendationStatus
    message: str


class TripTrackingResponse(BaseModel):
    id: UUID
    intent: TripIntent
    active: bool
    created_at: datetime
    last_checked_at: datetime
    summary: PriceSummary
    recommendation: Recommendation
    current_trip: BestTrip
    history: list[PricePoint]


class TrackingListResponse(BaseModel):
    items: list[TripTrackingResponse]


class HealthResponse(BaseModel):
    status: str
    provider: str
