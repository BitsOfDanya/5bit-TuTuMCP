from __future__ import annotations

from datetime import date, time
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class TransportMode(str, Enum):
    TRAIN = "train"
    FLIGHT = "flight"
    BUS = "bus"
    SUBURBAN_TRAIN = "suburban_train"


class ConstraintField(str, Enum):
    BUDGET = "budget"
    OUTBOUND_AFTER = "outbound_after"
    RETURN_BEFORE = "return_before"
    TRANSPORT = "transport"
    MAX_TRANSFERS = "max_transfers"


class TripSpec(BaseModel):
    origin: str = Field(min_length=2)
    destination: str = Field(min_length=2)

    outbound_date: date
    return_date: date

    outbound_after: time | None = None
    return_before: time | None = None

    travelers: int = Field(default=1, ge=1, le=9)
    budget: int | None = Field(default=None, gt=0)

    excluded_transport: list[TransportMode] = Field(default_factory=list)
    preferred_transport: list[TransportMode] = Field(default_factory=list)

    max_transfers: int | None = Field(default=None, ge=0, le=5)

    hard_constraints: set[ConstraintField] = Field(default_factory=set)

    @model_validator(mode="after")
    def validate_dates(self) -> "TripSpec":
        if self.return_date < self.outbound_date:
            raise ValueError(
                "return_date cannot be earlier than outbound_date"
            )

        return self