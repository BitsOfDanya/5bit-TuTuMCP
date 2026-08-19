from __future__ import annotations

from enum import Enum

from pydantic import (
    BaseModel,
    Field,
)

from app.models.journey import (
    JourneyOption,
)
from app.models.rescue import (
    RescueComponent,
    TripField,
)
from app.models.trip import (
    TripSpec,
)


class WhatIfStatus(
    str,
    Enum,
):
    NO_DIFFERENCE = (
        "no_difference"
    )

    ALTERNATIVES_FOUND = (
        "alternatives_found"
    )

    NEGOTIATION_REQUIRED = (
        "negotiation_required"
    )

    NO_ALTERNATIVES = (
        "no_alternatives"
    )


class WhatIfImpact(
    BaseModel
):
    """
    Difference between the currently accepted journey
    and one hypothetical candidate.

    Positive price_delta:
        candidate is more expensive.

    Negative price_delta:
        candidate is cheaper.

    Positive inbound_arrival_delta_minutes:
        candidate arrives later.

    Negative inbound_arrival_delta_minutes:
        candidate arrives earlier.
    """

    price_delta: int

    savings: int = Field(
        ge=0
    )

    price_change_percent: (
        float
        | None
    ) = None

    outbound_departure_delta_minutes: int

    inbound_arrival_delta_minutes: int

    components_changed: list[
        RescueComponent
    ] = Field(
        default_factory=list
    )

    components_preserved: list[
        RescueComponent
    ] = Field(
        default_factory=list
    )

    disruption_count: int = Field(
        ge=0
    )


class WhatIfCandidate(
    BaseModel
):
    id: str

    rank: int = Field(
        ge=1
    )

    journey: JourneyOption

    impact: WhatIfImpact


class WhatIfResult(
    BaseModel
):
    """
    Pure simulation result.

    Nothing in this object means that the current trip
    has been accepted, committed or persisted.
    """

    status: WhatIfStatus

    current_trip: TripSpec

    hypothetical_trip: TripSpec

    baseline_journey: JourneyOption

    changed_fields: list[
        TripField
    ] = Field(
        default_factory=list
    )

    baseline_valid: bool

    candidates: list[
        WhatIfCandidate
    ] = Field(
        default_factory=list
    )