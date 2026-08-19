from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from statistics import mean

from app.models.journey import (
    JourneyOption,
)
from app.preferences.models import (
    PreferenceAction,
    PreferenceLearningResult,
    PreferenceProfile,
    PreferenceWeights,
)
from app.preferences.store import (
    PreferenceStore,
    get_preference_store,
)


class PreferenceLearner:
    def __init__(
        self,
        store: PreferenceStore | None = None,
    ) -> None:
        self.store = (
            store
            or get_preference_store()
        )

    def learn(
        self,
        *,
        profile_id: str,
        action: PreferenceAction,
        candidate: JourneyOption,
        shown_candidates: list[
            JourneyOption
        ] | None = None,
    ) -> PreferenceLearningResult:
        profile = (
            self.store
            .get_or_create(
                profile_id
            )
        )

        signals: list[str] = []

        context = (
            shown_candidates
            or []
        )

        others = [
            journey
            for journey
            in context
            if journey.id
            != candidate.id
        ]

        self._update_mode_affinity(
            profile=profile,
            action=action,
            candidate=candidate,
            others=others,
            signals=signals,
        )

        if (
            action
            == PreferenceAction.CHOOSE
            and others
        ):
            self._learn_pairwise_weights(
                profile=profile,
                chosen=candidate,
                others=others,
                signals=signals,
            )

        profile.interactions += 1
        profile.version += 1

        action_key = (
            action.value
        )

        profile.action_counts[
            action_key
        ] = (
            profile.action_counts.get(
                action_key,
                0,
            )
            + 1
        )

        profile.updated_at = (
            datetime.now(
                timezone.utc
            )
        )

        saved = (
            self.store.save(
                profile
            )
        )

        return PreferenceLearningResult(
            profile=saved,
            learned_signals=signals,
        )

    def _update_mode_affinity(
        self,
        *,
        profile: PreferenceProfile,
        action: PreferenceAction,
        candidate: JourneyOption,
        others: list[
            JourneyOption
        ],
        signals: list[str],
    ) -> None:
        strengths = {
            PreferenceAction.LIKE: (
                0.20
            ),
            PreferenceAction.DISLIKE: (
                -0.22
            ),
            PreferenceAction.CHOOSE: (
                0.42
            ),
            PreferenceAction.REJECT: (
                -0.35
            ),
        }

        delta = strengths[
            action
        ]

        candidate_modes = (
            _journey_modes(
                candidate
            )
        )

        for mode in candidate_modes:
            previous = (
                profile
                .transport_affinity
                .get(
                    mode,
                    0.0,
                )
            )

            profile.transport_affinity[
                mode
            ] = round(
                _clamp(
                    previous + delta,
                    -2.0,
                    2.0,
                ),
                6,
            )

        labels = ", ".join(
            sorted(
                candidate_modes
            )
        )

        if delta > 0:
            signals.append(
                "Положительный сигнал "
                "для транспорта: "
                f"{labels}."
            )
        else:
            signals.append(
                "Отрицательный сигнал "
                "для транспорта: "
                f"{labels}."
            )

        # Explicit choose gives us a stronger
        # pairwise preference signal.
        if (
            action
            != PreferenceAction.CHOOSE
            or not others
        ):
            return

        other_modes: set[str] = set()

        for journey in others:
            other_modes.update(
                _journey_modes(
                    journey
                )
            )

        rejected_modes = (
            other_modes
            - candidate_modes
        )

        for mode in rejected_modes:
            previous = (
                profile
                .transport_affinity
                .get(
                    mode,
                    0.0,
                )
            )

            profile.transport_affinity[
                mode
            ] = round(
                _clamp(
                    previous - 0.10,
                    -2.0,
                    2.0,
                ),
                6,
            )

    def _learn_pairwise_weights(
        self,
        *,
        profile: PreferenceProfile,
        chosen: JourneyOption,
        others: list[
            JourneyOption
        ],
        signals: list[str],
    ) -> None:
        weights = (
            profile.weights
        )

        average_price = mean(
            journey.total_price
            for journey
            in others
        )

        average_duration = mean(
            _total_duration_minutes(
                journey
            )
            for journey
            in others
        )

        average_transfers = mean(
            _total_transfers(
                journey
            )
            for journey
            in others
        )

        chosen_price = (
            chosen.total_price
        )

        chosen_duration = (
            _total_duration_minutes(
                chosen
            )
        )

        chosen_transfers = (
            _total_transfers(
                chosen
            )
        )

        price_delta = (
            _relative_advantage(
                chosen=chosen_price,
                reference=average_price,
                lower_is_better=True,
            )
        )

        duration_delta = (
            _relative_advantage(
                chosen=chosen_duration,
                reference=average_duration,
                lower_is_better=True,
            )
        )

        transfer_delta = (
            _relative_advantage(
                chosen=chosen_transfers,
                reference=average_transfers,
                lower_is_better=True,
                zero_reference_scale=1.0,
            )
        )

        price_weight = (
            _update_importance(
                current=weights.price,
                evidence=price_delta,
                positive_rate=0.32,
                negative_rate=0.12,
            )
        )

        duration_weight = (
            _update_importance(
                current=(
                    weights.duration
                ),
                evidence=(
                    duration_delta
                ),
                positive_rate=0.28,
                negative_rate=0.10,
            )
        )

        transfers_weight = (
            _update_importance(
                current=(
                    weights.transfers
                ),
                evidence=(
                    transfer_delta
                ),
                positive_rate=0.30,
                negative_rate=0.10,
            )
        )

        hotel_weight = (
            weights.hotel_quality
        )

        chosen_hotel_rating = (
            _hotel_rating(
                chosen
            )
        )

        other_ratings = [
            rating
            for journey
            in others
            if (
                rating := (
                    _hotel_rating(
                        journey
                    )
                )
            )
            is not None
        ]

        if (
            chosen_hotel_rating
            is not None
            and other_ratings
        ):
            hotel_delta = (
                _relative_advantage(
                    chosen=(
                        chosen_hotel_rating
                    ),
                    reference=mean(
                        other_ratings
                    ),
                    lower_is_better=False,
                    zero_reference_scale=10.0,
                )
            )

            hotel_weight = (
                _update_importance(
                    current=(
                        weights
                        .hotel_quality
                    ),
                    evidence=(
                        hotel_delta
                    ),
                    positive_rate=0.22,
                    negative_rate=0.08,
                )
            )

            if hotel_delta > 0.05:
                signals.append(
                    "Похоже, качество "
                    "отеля для пользователя "
                    "важно."
                )

        profile.weights = (
            PreferenceWeights(
                price=price_weight,
                duration=duration_weight,
                transfers=(
                    transfers_weight
                ),
                hotel_quality=(
                    hotel_weight
                ),
            )
        )

        if price_delta > 0.05:
            signals.append(
                "Пользователь выбрал "
                "более выгодный вариант."
            )

        if duration_delta > 0.05:
            signals.append(
                "Пользователь выбрал "
                "более быстрый вариант."
            )

        if transfer_delta > 0.05:
            signals.append(
                "Пользователь предпочёл "
                "меньше пересадок."
            )


def _journey_modes(
    journey: JourneyOption,
) -> set[str]:
    return {
        journey.outbound.mode.value,
        journey.inbound.mode.value,
    }


def _total_duration_minutes(
    journey: JourneyOption,
) -> int:
    return (
        _segment_duration(
            journey.outbound
        )
        + _segment_duration(
            journey.inbound
        )
    )


def _segment_duration(
    segment,
) -> int:
    if (
        segment.duration_minutes
        is not None
    ):
        return max(
            segment.duration_minutes,
            0,
        )

    duration = (
        segment.arrival
        - segment.departure
    )

    return max(
        int(
            duration.total_seconds()
            // 60
        ),
        0,
    )


def _total_transfers(
    journey: JourneyOption,
) -> int:
    return (
        journey.outbound.transfers
        + journey.inbound.transfers
    )


def _hotel_rating(
    journey: JourneyOption,
) -> float | None:
    hotel = journey.hotel

    if (
        hotel is None
        or hotel.rating is None
    ):
        return None

    return float(
        hotel.rating
    )


def _relative_advantage(
    *,
    chosen: float,
    reference: float,
    lower_is_better: bool,
    zero_reference_scale: float = 1.0,
) -> float:
    denominator = max(
        abs(reference),
        zero_reference_scale,
    )

    difference = (
        reference - chosen
        if lower_is_better
        else chosen - reference
    )

    return _clamp(
        difference / denominator,
        -1.0,
        1.0,
    )


def _update_importance(
    *,
    current: float,
    evidence: float,
    positive_rate: float,
    negative_rate: float,
) -> float:
    if evidence >= 0:
        updated = (
            current
            + positive_rate
            * evidence
        )
    else:
        updated = (
            current
            + negative_rate
            * evidence
        )

    return round(
        _clamp(
            updated,
            0.0,
            2.0,
        ),
        6,
    )


def _clamp(
    value: float,
    low: float,
    high: float,
) -> float:
    return max(
        low,
        min(
            high,
            value,
        ),
    )


@lru_cache(maxsize=1)
def get_preference_learner() -> PreferenceLearner:
    return PreferenceLearner()