from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models.journey import JourneyOption
from app.models.trip import (
    ConstraintField,
    TripSpec,
)


class TripField(str, Enum):
    ORIGIN = "origin"
    DESTINATION = "destination"

    OUTBOUND_DATE = "outbound_date"
    RETURN_DATE = "return_date"

    OUTBOUND_AFTER = "outbound_after"
    RETURN_BEFORE = "return_before"

    TRAVELERS = "travelers"

    BUDGET = "budget"

    EXCLUDED_TRANSPORT = "excluded_transport"
    PREFERRED_TRANSPORT = "preferred_transport"

    MAX_TRANSFERS = "max_transfers"

    HARD_CONSTRAINTS = "hard_constraints"


class RescueComponent(str, Enum):
    OUTBOUND = "outbound"
    HOTEL = "hotel"
    INBOUND = "inbound"


class ComponentAction(str, Enum):
    PRESERVE = "preserve"
    REPLACE = "replace"


class RescuePlanReason(str, Enum):
    CONSTRAINT_VIOLATION = "constraint_violation"
    BUDGET_OPTIMIZATION = "budget_optimization"
    MIXED = "mixed"


class TripFieldChange(BaseModel):
    field: TripField

    old_value: Any = None
    new_value: Any = None

    affected_components: list[
        RescueComponent
    ] = Field(
        default_factory=list,
    )


class TripDiff(BaseModel):
    has_changes: bool

    changes: list[
        TripFieldChange
    ] = Field(
        default_factory=list,
    )

    changed_fields: list[
        TripField
    ] = Field(
        default_factory=list,
    )

    affected_components: list[
        RescueComponent
    ] = Field(
        default_factory=list,
    )


class ValidationReason(BaseModel):
    code: str
    message: str

    field: TripField | None = None


class ComponentValidation(BaseModel):
    component: RescueComponent

    action: ComponentAction

    valid: bool

    reasons: list[
        ValidationReason
    ] = Field(
        default_factory=list,
    )


class RescueValidation(BaseModel):
    journey_valid: bool

    components: list[
        ComponentValidation
    ] = Field(
        default_factory=list,
    )

    preserved_components: list[
        RescueComponent
    ] = Field(
        default_factory=list,
    )

    replace_components: list[
        RescueComponent
    ] = Field(
        default_factory=list,
    )

    budget_violation: bool = False

    budget_exceeded_by: int = Field(
        default=0,
        ge=0,
    )

    global_reasons: list[
        ValidationReason
    ] = Field(
        default_factory=list,
    )


class RescueSearchPlan(BaseModel):
    id: str

    reason: RescuePlanReason

    replace_components: list[
        RescueComponent
    ]

    preserve_components: list[
        RescueComponent
    ]

    mandatory_components: list[
        RescueComponent
    ] = Field(
        default_factory=list,
    )

    budget_target_saving: int = Field(
        default=0,
        ge=0,
    )

    score: float = Field(
        ge=0,
    )

    description: str


class RescuePlanningResult(BaseModel):
    status: Literal[
        "no_change",
        "search_required",
    ]

    plans: list[
        RescueSearchPlan
    ] = Field(
        default_factory=list,
    )


class RescueRelaxation(BaseModel):
    """
    One explicit compromise offered to the user.

    Hard constraints can never appear here.
    """

    field: ConstraintField

    title: str
    description: str

    old_value: Any = None
    new_value: Any = None

    magnitude: float = Field(
        default=0,
        ge=0,
    )

    score: float = Field(
        default=0,
        ge=0,
    )


class RescueCandidate(BaseModel):
    id: str

    search_plan_id: str

    replaced_components: list[
        RescueComponent
    ]

    preserved_components: list[
        RescueComponent
    ]

    journey: JourneyOption

    previous_total_price: int = Field(
        ge=0,
    )

    new_total_price: int = Field(
        ge=0,
    )

    price_delta: int

    score: float = Field(
        ge=0,
    )

    exact: bool = True

    relaxations: list[
        RescueRelaxation
    ] = Field(
        default_factory=list,
    )

    suggested_trip: TripSpec | None = None


class RescueExecutionResult(BaseModel):
    status: Literal[
        "no_change",
        "candidates_found",
        "negotiation_required",
        "no_candidates",
    ]

    candidates: list[
        RescueCandidate
    ] = Field(
        default_factory=list,
    )