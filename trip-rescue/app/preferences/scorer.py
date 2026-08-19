from __future__ import annotations

from dataclasses import dataclass

from app.models.journey import (
    JourneyOption,
)
from app.models.rescue import (
    RescueCandidate,
)
from app.preferences.models import (
    PreferenceProfile,
)


@dataclass(
    frozen=True,
    slots=True,
)
class CandidatePreferenceScore:
    candidate: RescueCandidate

    rank_before: int
    rank_after: int

    preference_score: float
    personalized_score: float

    reasons: tuple[
        str,
        ...
    ]


@dataclass(
    frozen=True,
    slots=True,
)
class JourneyPreferenceScore:
    journey: JourneyOption

    rank_before: int
    rank_after: int

    preference_score: float

    reasons: tuple[
        str,
        ...
    ]


@dataclass(
    frozen=True,
    slots=True,
)
class JourneyFeatures:
    price: float
    duration: float
    transfers: float
    hotel_quality: float

    modes: tuple[
        str,
        ...
    ]


def rerank_rescue_candidates(
    *,
    candidates: list[
        RescueCandidate
    ],
    profile: PreferenceProfile,
) -> list[
    CandidatePreferenceScore
]:

    if not candidates:
        return []

    journeys = [
        candidate.journey
        for candidate
        in candidates
    ]

    normalized = (
        _normalized_features(
            journeys
        )
    )

    scored: list[
        tuple[
            RescueCandidate,
            int,
            float,
            float,
            tuple[str, ...],
        ]
    ] = []

    strength = (
        _personalization_strength(
            profile.interactions
        )
    )

    for index, candidate in enumerate(
        candidates,
        start=1,
    ):
        features = normalized[
            candidate.journey.id
        ]

        preference_score, reasons = (
            _score_features(
                features=features,
                journey=(
                    candidate.journey
                ),
                profile=profile,
            )
        )

        personalized_score = (
            candidate.score
            - (
                strength
                * preference_score
            )
        )

        scored.append(
            (
                candidate,
                index,
                round(
                    preference_score,
                    6,
                ),
                round(
                    personalized_score,
                    6,
                ),
                reasons,
            )
        )

    scored.sort(
        key=lambda item: (
            item[3],
            item[0].score,
            item[0].new_total_price,
            item[0].id,
        )
    )

    return [
        CandidatePreferenceScore(
            candidate=item[0],
            rank_before=item[1],
            rank_after=rank_after,
            preference_score=item[2],
            personalized_score=item[3],
            reasons=item[4],
        )
        for rank_after, item
        in enumerate(
            scored,
            start=1,
        )
    ]


def rerank_journeys(
    *,
    journeys: list[
        JourneyOption
    ],
    profile: PreferenceProfile,
) -> list[
    JourneyPreferenceScore
]:

    if not journeys:
        return []

    normalized = (
        _normalized_features(
            journeys
        )
    )

    scored: list[
        tuple[
            JourneyOption,
            int,
            float,
            tuple[str, ...],
        ]
    ] = []

    for index, journey in enumerate(
        journeys,
        start=1,
    ):
        features = normalized[
            journey.id
        ]

        preference_score, reasons = (
            _score_features(
                features=features,
                journey=journey,
                profile=profile,
            )
        )

        scored.append(
            (
                journey,
                index,
                preference_score,
                reasons,
            )
        )

    scored.sort(
        key=lambda item: (
            -item[2],
            item[0].total_price,
            item[0].id,
        )
    )

    return [
        JourneyPreferenceScore(
            journey=item[0],
            rank_before=item[1],
            rank_after=rank_after,
            preference_score=round(
                item[2],
                6,
            ),
            reasons=item[3],
        )
        for rank_after, item
        in enumerate(
            scored,
            start=1,
        )
    ]


def _normalized_features(
    journeys: list[
        JourneyOption
    ],
) -> dict[
    str,
    JourneyFeatures,
]:

    prices = [
        float(
            journey.total_price
        )
        for journey
        in journeys
    ]

    durations = [
        float(
            _total_duration_minutes(
                journey
            )
        )
        for journey
        in journeys
    ]

    transfers = [
        float(
            _total_transfers(
                journey
            )
        )
        for journey
        in journeys
    ]

    result: dict[
        str,
        JourneyFeatures,
    ] = {}

    for journey in journeys:
        hotel_rating = (
            _hotel_rating(
                journey
            )
        )

        result[
            journey.id
        ] = JourneyFeatures(
            # All normalized values:
            # higher = better.
            price=(
                _lower_is_better_quality(
                    float(
                        journey.total_price
                    ),
                    prices,
                )
            ),
            duration=(
                _lower_is_better_quality(
                    float(
                        _total_duration_minutes(
                            journey
                        )
                    ),
                    durations,
                )
            ),
            transfers=(
                _lower_is_better_quality(
                    float(
                        _total_transfers(
                            journey
                        )
                    ),
                    transfers,
                )
            ),
            hotel_quality=(
                (
                    hotel_rating
                    / 10.0
                )
                if hotel_rating
                is not None
                else 0.5
            ),
            modes=tuple(
                sorted(
                    {
                        (
                            journey
                            .outbound
                            .mode
                            .value
                        ),
                        (
                            journey
                            .inbound
                            .mode
                            .value
                        ),
                    }
                )
            ),
        )

    return result


def _score_features(
    *,
    features: JourneyFeatures,
    journey: JourneyOption,
    profile: PreferenceProfile,
) -> tuple[
    float,
    tuple[str, ...],
]:

    weights = (
        profile.weights
    )

    contributions: list[
        tuple[
            float,
            str,
        ]
    ] = []

    price_contribution = (
        weights.price
        * features.price
    )

    duration_contribution = (
        weights.duration
        * features.duration
    )

    transfers_contribution = (
        weights.transfers
        * features.transfers
    )

    hotel_contribution = (
        weights.hotel_quality
        * features.hotel_quality
    )

    if price_contribution > 0.03:
        contributions.append(
            (
                price_contribution,
                (
                    "Соответствует твоей "
                    "привычке выбирать "
                    "более выгодные варианты."
                ),
            )
        )

    if (
        duration_contribution
        > 0.03
    ):
        contributions.append(
            (
                duration_contribution,
                (
                    "Подходит по привычной "
                    "для тебя длительности "
                    "дороги."
                ),
            )
        )

    if (
        transfers_contribution
        > 0.03
    ):
        contributions.append(
            (
                transfers_contribution,
                (
                    "Соответствует твоему "
                    "предпочтению меньшего "
                    "числа пересадок."
                ),
            )
        )

    if (
        hotel_contribution
        > 0.03
        and journey.hotel
        is not None
    ):
        contributions.append(
            (
                hotel_contribution,
                (
                    "Качество отеля "
                    "соответствует твоим "
                    "прошлым выборам."
                ),
            )
        )

    mode_values = [
        profile
        .transport_affinity
        .get(
            mode,
            0.0,
        )
        for mode
        in features.modes
    ]

    mode_affinity = (
        sum(mode_values)
        / len(mode_values)
        if mode_values
        else 0.0
    )

    mode_contribution = (
        mode_affinity
        * 0.55
    )

    if mode_affinity > 0.10:
        labels = ", ".join(
            _mode_label(
                mode
            )
            for mode
            in features.modes
        )

        contributions.append(
            (
                abs(
                    mode_contribution
                ),
                (
                    "Ты чаще положительно "
                    "оцениваешь транспорт: "
                    f"{labels}."
                ),
            )
        )

    elif mode_affinity < -0.10:
        labels = ", ".join(
            _mode_label(
                mode
            )
            for mode
            in features.modes
        )

        contributions.append(
            (
                abs(
                    mode_contribution
                ),
                (
                    "Этот транспорт ты "
                    "раньше чаще отклонял: "
                    f"{labels}."
                ),
            )
        )

    total = (
        price_contribution
        + duration_contribution
        + transfers_contribution
        + hotel_contribution
        + mode_contribution
    )

    contributions.sort(
        key=lambda item: (
            -item[0]
        )
    )

    reasons = tuple(
        item[1]
        for item
        in contributions[:3]
    )

    return (
        round(
            total,
            6,
        ),
        reasons,
    )


def _personalization_strength(
    interactions: int,
) -> float:
    if interactions <= 0:
        return 0.0

    # Personalization grows gradually.
    #
    # It can reorder close candidates,
    # but cannot overwhelm the core Rescue score.
    return min(
        0.45,
        0.10
        + interactions
        * 0.035,
    )


def _lower_is_better_quality(
    value: float,
    population: list[
        float
    ],
) -> float:
    minimum = min(
        population
    )

    maximum = max(
        population
    )

    if maximum == minimum:
        return 0.5

    normalized = (
        value - minimum
    ) / (
        maximum - minimum
    )

    return (
        1.0
        - normalized
    )


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

    return max(
        int(
            (
                segment.arrival
                - segment.departure
            ).total_seconds()
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


def _mode_label(
    mode: str,
) -> str:
    labels = {
        "bus": "автобус",
        "train": "поезд",
        "flight": "самолёт",
        "suburban_train": (
            "электричка"
        ),
    }

    return labels.get(
        mode,
        mode,
    )