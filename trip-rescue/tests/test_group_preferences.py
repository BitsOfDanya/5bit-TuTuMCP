from __future__ import annotations

import pytest

from app.preferences.group import (
    build_group_preference_profile,
)
from app.preferences.models import (
    PreferenceProfile,
    PreferenceWeights,
)


def _profile(
    profile_id: str,
    *,
    price: float = 0.0,
    duration: float = 0.0,
    transfers: float = 0.0,
    hotel_quality: float = 0.0,
    transport_affinity: (
        dict[str, float]
        | None
    ) = None,
    interactions: int = 4,
) -> PreferenceProfile:
    return PreferenceProfile(
        profile_id=profile_id,
        interactions=interactions,
        weights=PreferenceWeights(
            price=price,
            duration=duration,
            transfers=transfers,
            hotel_quality=(
                hotel_quality
            ),
        ),
        transport_affinity=(
            transport_affinity
            or {}
        ),
    )


def test_builds_group_profile() -> None:
    result = (
        build_group_preference_profile(
            group_id="weekend",
            profiles=[
                _profile(
                    "danya",
                    price=1.5,
                    duration=0.3,
                ),
                _profile(
                    "misha",
                    price=0.5,
                    duration=1.3,
                ),
            ],
        )
    )

    assert (
        result.group_id
        == "weekend"
    )

    assert (
        result.member_count
        == 2
    )

    assert (
        result.profile.profile_id
        == "group:weekend"
    )


def test_group_weights_are_compromise() -> None:
    result = (
        build_group_preference_profile(
            group_id="friends",
            profiles=[
                _profile(
                    "a",
                    price=1.5,
                ),
                _profile(
                    "b",
                    price=0.5,
                ),
                _profile(
                    "c",
                    price=1.0,
                ),
            ],
        )
    )

    assert (
        0.8
        <= result.profile.weights.price
        <= 1.2
    )


def test_extreme_member_does_not_dominate() -> None:
    result = (
        build_group_preference_profile(
            group_id="friends",
            profiles=[
                _profile(
                    "a",
                    price=0.4,
                ),
                _profile(
                    "b",
                    price=0.5,
                ),
                _profile(
                    "c",
                    price=2.0,
                ),
            ],
        )
    )

    assert (
        result.profile.weights.price
        < 1.1
    )


def test_transport_is_aggregated() -> None:
    result = (
        build_group_preference_profile(
            group_id="friends",
            profiles=[
                _profile(
                    "a",
                    transport_affinity={
                        "train": 1.4,
                    },
                ),
                _profile(
                    "b",
                    transport_affinity={
                        "train": 0.8,
                    },
                ),
            ],
        )
    )

    assert (
        result
        .profile
        .transport_affinity[
            "train"
        ]
        > 0
    )


def test_transport_conflict_is_detected() -> None:
    result = (
        build_group_preference_profile(
            group_id="friends",
            profiles=[
                _profile(
                    "a",
                    transport_affinity={
                        "flight": 1.5,
                    },
                ),
                _profile(
                    "b",
                    transport_affinity={
                        "flight": -1.2,
                    },
                ),
            ],
        )
    )

    conflict = next(
        value
        for value
        in result.conflicts
        if (
            value.dimension
            == "transport:flight"
        )
    )

    assert (
        conflict.severity
        == "high"
    )

    assert (
        result.consensus_score
        < 1.0
    )


def test_weight_conflict_is_detected() -> None:
    result = (
        build_group_preference_profile(
            group_id="friends",
            profiles=[
                _profile(
                    "a",
                    price=1.8,
                ),
                _profile(
                    "b",
                    price=0.2,
                ),
            ],
        )
    )

    assert any(
        conflict.dimension
        == "price"
        for conflict
        in result.conflicts
    )


def test_duplicate_profile_is_counted_once() -> None:
    first = _profile(
        "danya",
        price=1.0,
    )

    second = _profile(
        "misha",
        price=0.8,
    )

    result = (
        build_group_preference_profile(
            group_id="friends",
            profiles=[
                first,
                first,
                second,
            ],
        )
    )

    assert (
        result.member_count
        == 2
    )


def test_average_interactions_are_used() -> None:
    result = (
        build_group_preference_profile(
            group_id="friends",
            profiles=[
                _profile(
                    "a",
                    interactions=4,
                ),
                _profile(
                    "b",
                    interactions=8,
                ),
            ],
        )
    )

    assert (
        result.profile.interactions
        == 6
    )


def test_requires_two_profiles() -> None:
    with pytest.raises(
        ValueError,
        match="At least two",
    ):
        build_group_preference_profile(
            group_id="friends",
            profiles=[
                _profile(
                    "a"
                )
            ],
        )


def test_empty_group_id_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="group_id",
    ):
        build_group_preference_profile(
            group_id="   ",
            profiles=[
                _profile(
                    "a"
                ),
                _profile(
                    "b"
                ),
            ],
        )


def test_highlights_are_generated() -> None:
    result = (
        build_group_preference_profile(
            group_id="friends",
            profiles=[
                _profile(
                    "a",
                    price=1.5,
                ),
                _profile(
                    "b",
                    price=1.3,
                ),
            ],
        )
    )

    assert (
        result.highlights
    )