from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)

from pydantic import (
    BaseModel,
    Field,
)

from app.preferences.cold_start import (
    ColdStartChoice,
    ColdStartResult,
    evaluate_cold_start,
)
from app.preferences.models import (
    PreferenceProfile,
    PreferenceWeights,
)
from app.preferences.store import (
    PreferenceStore,
    get_preference_store,
)


class ColdStartCompletion(
    BaseModel
):
    profile: PreferenceProfile

    cold_start: ColdStartResult

    learned_signals: list[
        str
    ] = Field(
        default_factory=list
    )


class ColdStartService:
    """
    Applies Cold Start calibration to the same
    PreferenceProfile that is later consumed by
    the existing personalization scorer.

    No parallel user-profile system is created.
    """

    def __init__(
        self,
        *,
        store: (
            PreferenceStore
            | None
        ) = None,
    ) -> None:
        self.store = (
            store
            or get_preference_store()
        )

    def complete(
        self,
        *,
        profile_id: str,
        choices: list[
            ColdStartChoice
        ],
        replace: bool = False,
    ) -> ColdStartCompletion:
        result = (
            evaluate_cold_start(
                choices=choices
            )
        )

        if not result.completed:
            raise ValueError(
                "At least 4 Cold Start "
                "choices are required"
            )

        profile = (
            self.store
            .get_or_create(
                profile_id
            )
        )

        if (
            profile
            .cold_start_completed
            and not replace
        ):
            raise ValueError(
                "Cold Start is already "
                "completed for this profile"
            )

        previous_answers = (
            profile.cold_start_answers
            if (
                profile
                .cold_start_completed
            )
            else 0
        )

        profile.weights = (
            _merge_weights(
                current=profile.weights,
                cold=result.weights,
                existing_interactions=(
                    max(
                        0,
                        (
                            profile.interactions
                            - previous_answers
                        ),
                    )
                ),
            )
        )

        profile.transport_affinity = (
            _merge_transport_affinity(
                current=(
                    profile
                    .transport_affinity
                ),
                cold=(
                    result
                    .transport_affinity
                ),
                replace_cold=(
                    profile
                    .cold_start_completed
                ),
            )
        )

        # Cold Start answers are actual preference
        # interactions. This also lets the existing
        # personalization strength become useful
        # on the first real trip.
        if (
            profile
            .cold_start_completed
        ):
            profile.interactions = max(
                0,
                (
                    profile.interactions
                    - previous_answers
                ),
            )

        profile.interactions += (
            result.questions_answered
        )

        profile.action_counts[
            "cold_start"
        ] = (
            result.questions_answered
        )

        profile.cold_start_completed = (
            True
        )

        profile.cold_start_answers = (
            result.questions_answered
        )

        profile.cold_start_confidence = (
            result.confidence
        )

        profile.cold_start_completed_at = (
            datetime.now(
                timezone.utc
            )
        )

        profile.version += 1

        profile.updated_at = (
            datetime.now(
                timezone.utc
            )
        )

        saved = self.store.save(
            profile
        )

        learned_signals = [
            signal.reason
            for signal
            in result.signals
        ]

        return ColdStartCompletion(
            profile=saved,
            cold_start=result,
            learned_signals=(
                _deduplicate(
                    learned_signals
                )
            ),
        )


def _merge_weights(
    *,
    current: PreferenceWeights,
    cold,
    existing_interactions: int,
) -> PreferenceWeights:
    """
    New profile:
        Cold Start becomes initial preference state.

    Existing learned profile:
        Cold Start is blended instead of destroying
        behavioural learning that already exists.
    """

    if existing_interactions <= 0:
        return PreferenceWeights(
            price=cold.price,
            duration=cold.duration,
            transfers=(
                cold.transfers
            ),
            hotel_quality=(
                cold.hotel_quality
            ),
        )

    # Existing real behaviour should dominate.
    #
    # At 1-3 previous interactions Cold Start still
    # matters substantially.
    #
    # With more behavioural history its influence
    # becomes progressively smaller.
    cold_share = max(
        0.20,
        min(
            0.45,
            (
                0.50
                - existing_interactions
                * 0.025
            ),
        ),
    )

    existing_share = (
        1.0
        - cold_share
    )

    return PreferenceWeights(
        price=_blend(
            current.price,
            cold.price,
            existing_share,
            cold_share,
        ),
        duration=_blend(
            current.duration,
            cold.duration,
            existing_share,
            cold_share,
        ),
        transfers=_blend(
            current.transfers,
            cold.transfers,
            existing_share,
            cold_share,
        ),
        hotel_quality=_blend(
            current.hotel_quality,
            cold.hotel_quality,
            existing_share,
            cold_share,
        ),
    )


def _merge_transport_affinity(
    *,
    current: dict[
        str,
        float,
    ],
    cold: dict[
        str,
        float,
    ],
    replace_cold: bool,
) -> dict[
    str,
    float,
]:
    """
    Transport affinity uses the same [-2, 2] range
    as the existing learner.

    For a fresh profile we simply seed it.

    For an existing profile we add a moderate Cold Start
    signal rather than replacing learned behaviour.
    """

    if not current:
        return {
            mode: round(
                _clamp(
                    value,
                    -2.0,
                    2.0,
                ),
                6,
            )
            for mode, value
            in cold.items()
        }

    result = dict(
        current
    )

    cold_factor = (
        0.50
        if replace_cold
        else 0.65
    )

    for mode, value in (
        cold.items()
    ):
        previous = result.get(
            mode,
            0.0,
        )

        result[mode] = round(
            _clamp(
                (
                    previous
                    + value
                    * cold_factor
                ),
                -2.0,
                2.0,
            ),
            6,
        )

    return result


def _blend(
    current: float,
    cold: float,
    existing_share: float,
    cold_share: float,
) -> float:
    value = (
        current
        * existing_share
        + cold
        * cold_share
    )

    return round(
        _clamp(
            value,
            0.0,
            2.0,
        ),
        6,
    )


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


def _deduplicate(
    values: list[str],
) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []

    for value in values:
        clean = value.strip()

        if (
            not clean
            or clean in seen
        ):
            continue

        seen.add(
            clean
        )

        result.append(
            clean
        )

    return result