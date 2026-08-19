from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models.journey import JourneyOption
from app.models.trip import ConstraintField, TripSpec


class ConstraintChange(BaseModel):
    field: ConstraintField

    title: str
    description: str

    old_value: Any = None
    new_value: Any = None

    magnitude: float = Field(ge=0)


class RelaxationPlan(BaseModel):
    id: str

    changes: list[ConstraintChange]

    score: float = Field(ge=0)

    journey: JourneyOption


class NegotiationResult(BaseModel):
    status: Literal[
        "success",
        "negotiation_required",
        "no_options",
    ]

    trip_spec: TripSpec

    journeys: list[JourneyOption] = Field(default_factory=list)

    alternatives: list[RelaxationPlan] = Field(default_factory=list)