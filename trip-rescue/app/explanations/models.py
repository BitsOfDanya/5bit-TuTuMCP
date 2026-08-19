from __future__ import annotations

from enum import Enum

from pydantic import (
    BaseModel,
    Field,
)

from app.models.rescue import (
    RescueComponent,
)


class ExplanationType(
    str,
    Enum,
):
    PRESERVATION = "preservation"
    CONSTRAINT = "constraint"
    PRICE = "price"
    SCHEDULE = "schedule"
    PREFERENCE = "preference"
    INSIGHT = "insight"
    TRADEOFF = "tradeoff"


class ExplanationItem(
    BaseModel
):
    type: ExplanationType

    text: str

    positive: bool = True


class DecisionExplanation(
    BaseModel
):
    headline: str

    summary: str

    reasons: list[
        ExplanationItem
    ] = Field(
        default_factory=list
    )

    tradeoffs: list[
        ExplanationItem
    ] = Field(
        default_factory=list
    )

    preserved_components: list[
        RescueComponent
    ] = Field(
        default_factory=list
    )

    changed_components: list[
        RescueComponent
    ] = Field(
        default_factory=list
    )