from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class PreferenceAction(str, Enum):
    LIKE = "like"
    DISLIKE = "dislike"

    CHOOSE = "choose"
    REJECT = "reject"


class PreferenceWeights(BaseModel):
    """
    Learned importance of generic journey properties.

    0 means:
        no learned preference yet.

    Higher value means:
        this characteristic matters more
        for this user.
    """

    price: float = Field(
        default=0.0,
        ge=0.0,
        le=2.0,
    )

    duration: float = Field(
        default=0.0,
        ge=0.0,
        le=2.0,
    )

    transfers: float = Field(
        default=0.0,
        ge=0.0,
        le=2.0,
    )

    hotel_quality: float = Field(
        default=0.0,
        ge=0.0,
        le=2.0,
    )


class PreferenceProfile(BaseModel):
    profile_id: str

    version: int = Field(
        default=1,
        ge=1,
    )

    interactions: int = Field(
        default=0,
        ge=0,
    )

    weights: PreferenceWeights = Field(
        default_factory=PreferenceWeights
    )

    # Keys are transport mode values:
    #
    # bus
    # train
    # flight
    # suburban_train
    #
    # Range:
    # -2 = strong dislike
    # +2 = strong preference
    transport_affinity: dict[
        str,
        float,
    ] = Field(
        default_factory=dict
    )

    action_counts: dict[
        str,
        int,
    ] = Field(
        default_factory=dict
    )

    updated_at: datetime = Field(
        default_factory=lambda: (
            datetime.now(
                timezone.utc
            )
        )
    )


class PreferenceLearningResult(BaseModel):
    profile: PreferenceProfile

    learned_signals: list[
        str
    ] = Field(
        default_factory=list
    )