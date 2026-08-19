from __future__ import annotations

from pydantic import (
    BaseModel,
    Field,
)

from app.preferences.models import (
    PreferenceProfile,
    PreferenceWeights,
)


class GroupPreferenceConflict(
    BaseModel
):
    dimension: str

    spread: float = Field(
        ge=0.0,
    )

    severity: str

    description: str


class GroupPreferenceSummary(
    BaseModel
):
    group_id: str

    member_count: int = Field(
        ge=2,
    )

    member_profile_ids: list[
        str
    ]

    profile: PreferenceProfile

    conflicts: list[
        GroupPreferenceConflict
    ] = Field(
        default_factory=list
    )

    consensus_score: float = Field(
        ge=0.0,
        le=1.0,
    )

    highlights: list[
        str
    ] = Field(
        default_factory=list
    )


def build_group_preference_profile(
    *,
    group_id: str,
    profiles: list[
        PreferenceProfile
    ],
) -> GroupPreferenceSummary:
    """
    Build a virtual group preference profile.

    Important:
    - individual profiles are not mutated;
    - group profile is not persisted;
    - every group member has equal influence;
    - existing personalization scorer can consume
      the resulting PreferenceProfile directly.
    """

    clean_group_id = (
        group_id.strip()
    )

    if not clean_group_id:
        raise ValueError(
            "group_id cannot be empty"
        )

    unique_profiles = (
        _deduplicate_profiles(
            profiles
        )
    )

    if len(unique_profiles) < 2:
        raise ValueError(
            "At least two unique preference "
            "profiles are required"
        )

    weights = (
        _aggregate_weights(
            unique_profiles
        )
    )

    transport_affinity = (
        _aggregate_transport_affinity(
            unique_profiles
        )
    )

    conflicts = (
        _detect_conflicts(
            unique_profiles
        )
    )

    interactions = int(
        round(
            _mean(
                [
                    float(
                        profile.interactions
                    )
                    for profile
                    in unique_profiles
                ]
            )
        )
    )

    cold_start_answers = int(
        round(
            _mean(
                [
                    float(
                        profile
                        .cold_start_answers
                    )
                    for profile
                    in unique_profiles
                ]
            )
        )
    )

    cold_start_confidence = (
        _mean(
            [
                profile
                .cold_start_confidence
                for profile
                in unique_profiles
            ]
        )
    )

    group_profile = (
        PreferenceProfile(
            profile_id=(
                f"group:{clean_group_id}"
            ),
            interactions=max(
                interactions,
                0,
            ),
            weights=weights,
            transport_affinity=(
                transport_affinity
            ),
            action_counts={
                "group_members": (
                    len(
                        unique_profiles
                    )
                )
            },
            cold_start_completed=(
                all(
                    profile
                    .cold_start_completed
                    for profile
                    in unique_profiles
                )
            ),
            cold_start_answers=max(
                cold_start_answers,
                0,
            ),
            cold_start_confidence=(
                round(
                    _clamp(
                        cold_start_confidence,
                        0.0,
                        1.0,
                    ),
                    4,
                )
            ),
        )
    )

    return GroupPreferenceSummary(
        group_id=clean_group_id,
        member_count=len(
            unique_profiles
        ),
        member_profile_ids=[
            profile.profile_id
            for profile
            in unique_profiles
        ],
        profile=group_profile,
        conflicts=conflicts,
        consensus_score=(
            _build_consensus_score(
                conflicts
            )
        ),
        highlights=(
            _build_highlights(
                weights=weights,
                transport_affinity=(
                    transport_affinity
                ),
            )
        ),
    )


def _deduplicate_profiles(
    profiles: list[
        PreferenceProfile
    ],
) -> list[
    PreferenceProfile
]:
    seen: set[str] = set()

    result: list[
        PreferenceProfile
    ] = []

    for profile in profiles:
        profile_id = (
            profile.profile_id.strip()
        )

        if not profile_id:
            raise ValueError(
                "profile_id cannot be empty"
            )

        if profile_id in seen:
            continue

        seen.add(
            profile_id
        )

        result.append(
            profile.model_copy(
                deep=True
            )
        )

    return result


def _aggregate_weights(
    profiles: list[
        PreferenceProfile
    ],
) -> PreferenceWeights:
    return PreferenceWeights(
        price=(
            _robust_average(
                [
                    profile.weights.price
                    for profile
                    in profiles
                ]
            )
        ),
        duration=(
            _robust_average(
                [
                    profile.weights.duration
                    for profile
                    in profiles
                ]
            )
        ),
        transfers=(
            _robust_average(
                [
                    profile.weights.transfers
                    for profile
                    in profiles
                ]
            )
        ),
        hotel_quality=(
            _robust_average(
                [
                    profile
                    .weights
                    .hotel_quality
                    for profile
                    in profiles
                ]
            )
        ),
    )


def _aggregate_transport_affinity(
    profiles: list[
        PreferenceProfile
    ],
) -> dict[
    str,
    float,
]:
    modes: set[str] = set()

    for profile in profiles:
        modes.update(
            profile
            .transport_affinity
            .keys()
        )

    result: dict[
        str,
        float,
    ] = {}

    for mode in sorted(
        modes
    ):
        values = [
            profile
            .transport_affinity
            .get(
                mode,
                0.0,
            )
            for profile
            in profiles
        ]

        value = (
            _robust_average(
                values
            )
        )

        if abs(value) < 0.05:
            continue

        result[mode] = round(
            _clamp(
                value,
                -2.0,
                2.0,
            ),
            6,
        )

    return result


def _detect_conflicts(
    profiles: list[
        PreferenceProfile
    ],
) -> list[
    GroupPreferenceConflict
]:
    conflicts: list[
        GroupPreferenceConflict
    ] = []

    dimensions: dict[
        str,
        list[float],
    ] = {
        "price": [
            profile.weights.price
            for profile
            in profiles
        ],
        "duration": [
            profile.weights.duration
            for profile
            in profiles
        ],
        "transfers": [
            profile.weights.transfers
            for profile
            in profiles
        ],
        "hotel_quality": [
            profile
            .weights
            .hotel_quality
            for profile
            in profiles
        ],
    }

    labels = {
        "price": "цены",
        "duration": (
            "длительности поездки"
        ),
        "transfers": (
            "количества пересадок"
        ),
        "hotel_quality": (
            "качества отеля"
        ),
    }

    for (
        dimension,
        values,
    ) in dimensions.items():
        spread = (
            max(values)
            - min(values)
        )

        if spread < 0.75:
            continue

        severity = (
            "high"
            if spread >= 1.25
            else "medium"
        )

        conflicts.append(
            GroupPreferenceConflict(
                dimension=dimension,
                spread=round(
                    spread,
                    4,
                ),
                severity=severity,
                description=(
                    "У участников заметно "
                    "различается важность "
                    f"{labels[dimension]}."
                ),
            )
        )

    transport_modes: set[str] = set()

    for profile in profiles:
        transport_modes.update(
            profile
            .transport_affinity
            .keys()
        )

    for mode in sorted(
        transport_modes
    ):
        values = [
            profile
            .transport_affinity
            .get(
                mode,
                0.0,
            )
            for profile
            in profiles
        ]

        spread = (
            max(values)
            - min(values)
        )

        positive = any(
            value >= 0.5
            for value
            in values
        )

        negative = any(
            value <= -0.5
            for value
            in values
        )

        if (
            spread < 1.0
            and not (
                positive
                and negative
            )
        ):
            continue

        severity = (
            "high"
            if (
                (
                    positive
                    and negative
                )
                or spread >= 2.0
            )
            else "medium"
        )

        conflicts.append(
            GroupPreferenceConflict(
                dimension=(
                    f"transport:{mode}"
                ),
                spread=round(
                    spread,
                    4,
                ),
                severity=severity,
                description=(
                    "Участники по-разному "
                    "относятся к виду "
                    f"транспорта: {mode}."
                ),
            )
        )

    return conflicts


def _build_consensus_score(
    conflicts: list[
        GroupPreferenceConflict
    ],
) -> float:
    penalty = 0.0

    for conflict in conflicts:
        if (
            conflict.severity
            == "high"
        ):
            penalty += 0.18

        else:
            penalty += 0.09

    return round(
        _clamp(
            1.0 - penalty,
            0.0,
            1.0,
        ),
        4,
    )


def _build_highlights(
    *,
    weights: PreferenceWeights,
    transport_affinity: dict[
        str,
        float,
    ],
) -> list[str]:
    highlights: list[str] = []

    dimensions = [
        (
            "price",
            weights.price,
            (
                "Для группы заметно "
                "важна стоимость."
            ),
        ),
        (
            "duration",
            weights.duration,
            (
                "Для группы заметно "
                "важно время в пути."
            ),
        ),
        (
            "transfers",
            weights.transfers,
            (
                "Группа предпочитает "
                "минимум пересадок."
            ),
        ),
        (
            "hotel_quality",
            weights.hotel_quality,
            (
                "Для группы важно "
                "качество отеля."
            ),
        ),
    ]

    strongest = max(
        dimensions,
        key=lambda item: item[1],
    )

    if strongest[1] >= 0.5:
        highlights.append(
            strongest[2]
        )

    if transport_affinity:
        mode, affinity = max(
            transport_affinity.items(),
            key=lambda item: (
                abs(item[1])
            ),
        )

        if affinity >= 0.5:
            highlights.append(
                "Группа в целом "
                f"предпочитает {mode}."
            )

        elif affinity <= -0.5:
            highlights.append(
                "Группа в целом "
                f"избегает {mode}."
            )

    return highlights


def _robust_average(
    values: list[float],
) -> float:
    """
    70% arithmetic mean + 30% median.

    This keeps every member important while reducing
    the effect of one extreme preference.
    """

    if not values:
        return 0.0

    if len(values) == 1:
        return round(
            values[0],
            6,
        )

    value = (
        _mean(values)
        * 0.70
        + _median(values)
        * 0.30
    )

    return round(
        value,
        6,
    )


def _mean(
    values: list[float],
) -> float:
    if not values:
        return 0.0

    return (
        sum(values)
        / len(values)
    )


def _median(
    values: list[float],
) -> float:
    ordered = sorted(
        values
    )

    middle = (
        len(ordered)
        // 2
    )

    if (
        len(ordered)
        % 2
        == 1
    ):
        return ordered[
            middle
        ]

    return (
        ordered[
            middle - 1
        ]
        + ordered[
            middle
        ]
    ) / 2


def _clamp(
    value: float,
    minimum: float,
    maximum: float,
) -> float:
    return max(
        minimum,
        min(
            maximum,
            value,
        ),
    )