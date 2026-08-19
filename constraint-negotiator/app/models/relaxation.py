from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models.journey import JourneyOption
from app.models.trip import (
    ConstraintField,
    TripSpec,
)


class ConstraintChange(BaseModel):
    field: ConstraintField

    title: str
    description: str

    old_value: Any = None
    new_value: Any = None

    magnitude: float = Field(
        ge=0
    )


class RelaxationSummary(BaseModel):
    """
    Frontend-ready representation of a proposal.

    Frontend should not reconstruct human-readable
    travel information from raw MCP fields.
    """

    headline: str

    explanation: str

    total_price: int = Field(
        ge=0
    )

    transport_price: int = Field(
        ge=0
    )

    hotel_price: int = Field(
        ge=0
    )

    outbound_label: str
    inbound_label: str

    hotel_label: str | None = None


class RelaxationPlan(BaseModel):
    id: str

    kind: Literal[
        "single",
        "combination",
    ]

    changes: list[ConstraintChange]

    score: float = Field(
        ge=0
    )

    new_trip_spec: TripSpec

    journey: JourneyOption

    summary: RelaxationSummary | None = None


class NegotiationResult(BaseModel):
    status: Literal[
        "success",
        "negotiation_required",
        "no_options",
    ]

    trip_spec: TripSpec

    journeys: list[JourneyOption] = Field(
        default_factory=list
    )

    alternatives: list[RelaxationPlan] = Field(
        default_factory=list
    )