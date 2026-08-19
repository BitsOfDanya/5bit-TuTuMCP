from __future__ import annotations

from enum import Enum

from pydantic import (
    BaseModel,
    Field,
)

from app.models.trip import (
    TransportMode,
)


class ColdStartDimension(
    str,
    Enum,
):
    PRICE = "price"
    DURATION = "duration"
    TRANSFERS = "transfers"
    HOTEL_QUALITY = "hotel_quality"
    TRANSPORT = "transport"


class ColdStartOption(
    BaseModel
):
    id: str

    title: str
    subtitle: str

    total_price: int = Field(
        ge=0
    )

    duration_minutes: int = Field(
        ge=0
    )

    transfers: int = Field(
        ge=0
    )

    transport: TransportMode

    hotel_rating: (
        float
        | None
    ) = Field(
        default=None,
        ge=0,
        le=10,
    )


class ColdStartQuestion(
    BaseModel
):
    id: str

    prompt: str

    left: ColdStartOption
    right: ColdStartOption

    targets: list[
        ColdStartDimension
    ]


class ColdStartChoice(
    BaseModel
):
    question_id: str

    selected_option_id: str


class ColdStartWeights(
    BaseModel
):
    price: float = Field(
        default=0.0,
        ge=0,
        le=2,
    )

    duration: float = Field(
        default=0.0,
        ge=0,
        le=2,
    )

    transfers: float = Field(
        default=0.0,
        ge=0,
        le=2,
    )

    hotel_quality: float = Field(
        default=0.0,
        ge=0,
        le=2,
    )


class ColdStartSignal(
    BaseModel
):
    dimension: (
        ColdStartDimension
    )

    direction: str

    strength: float

    reason: str


class ColdStartResult(
    BaseModel
):
    questions_answered: int = Field(
        ge=0
    )

    total_questions: int = Field(
        ge=1
    )

    completed: bool

    confidence: float = Field(
        ge=0,
        le=1,
    )

    weights: ColdStartWeights

    transport_affinity: dict[
        str,
        float,
    ] = Field(
        default_factory=dict
    )

    signals: list[
        ColdStartSignal
    ] = Field(
        default_factory=list
    )


DEFAULT_MIN_CHOICES = 4


def get_cold_start_questions(
    *,
    limit: int = 6,
) -> list[
    ColdStartQuestion
]:
    """
    Controlled synthetic comparisons.

    They intentionally do not depend on live Tutu inventory.

    Reason:
    Cold Start should measure the user's decision style,
    not today's random availability or ticket prices.

    Real Tutu candidates will use the resulting profile later.
    """

    questions = [
        _price_vs_speed(),
        _direct_vs_cheaper(),
        _train_vs_flight(),
        _hotel_quality_vs_price(),
        _arrival_time_vs_price(),
        _direct_flight_vs_connection(),
    ]

    clean_limit = max(
        0,
        min(
            limit,
            len(questions),
        ),
    )

    return questions[
        :clean_limit
    ]


def evaluate_cold_start(
    *,
    choices: list[
        ColdStartChoice
    ],
    questions: (
        list[
            ColdStartQuestion
        ]
        | None
    ) = None,
    minimum_choices: int = (
        DEFAULT_MIN_CHOICES
    ),
) -> ColdStartResult:
    active_questions = (
        questions
        if questions is not None
        else get_cold_start_questions()
    )

    if not active_questions:
        raise ValueError(
            "Cold Start questions are empty"
        )

    question_map = {
        question.id: question
        for question
        in active_questions
    }

    seen_questions: set[
        str
    ] = set()

    price_score = 0.0
    duration_score = 0.0
    transfers_score = 0.0
    hotel_quality_score = 0.0

    transport_affinity: dict[
        str,
        float,
    ] = {}

    signals: list[
        ColdStartSignal
    ] = []

    for choice in choices:
        if (
            choice.question_id
            in seen_questions
        ):
            raise ValueError(
                "Duplicate Cold Start "
                f"question: "
                f"{choice.question_id}"
            )

        question = (
            question_map.get(
                choice.question_id
            )
        )

        if question is None:
            raise ValueError(
                "Unknown Cold Start "
                f"question: "
                f"{choice.question_id}"
            )

        seen_questions.add(
            choice.question_id
        )

        selected, rejected = (
            _resolve_choice(
                question=question,
                selected_option_id=(
                    choice
                    .selected_option_id
                ),
            )
        )

        targets = set(
            question.targets
        )

        # -----------------------------------------------------
        # Price
        # -----------------------------------------------------

        if (
            ColdStartDimension.PRICE
            in targets
        ):
            delta = (
                _relative_advantage(
                    better=(
                        rejected.total_price
                    ),
                    worse=(
                        selected.total_price
                    ),
                    lower_is_better=True,
                )
            )

            if (
                selected.total_price
                < rejected.total_price
            ):
                strength = (
                    0.35
                    + 0.55
                    * delta
                )

                price_score += strength

                signals.append(
                    ColdStartSignal(
                        dimension=(
                            ColdStartDimension
                            .PRICE
                        ),
                        direction=(
                            "prefer_lower"
                        ),
                        strength=round(
                            strength,
                            4,
                        ),
                        reason=(
                            "Пользователь выбрал "
                            "более дешёвый вариант."
                        ),
                    )
                )

            elif (
                selected.total_price
                > rejected.total_price
            ):
                strength = (
                    0.20
                    + 0.35
                    * delta
                )

                price_score -= strength

                signals.append(
                    ColdStartSignal(
                        dimension=(
                            ColdStartDimension
                            .PRICE
                        ),
                        direction=(
                            "accept_higher"
                        ),
                        strength=round(
                            strength,
                            4,
                        ),
                        reason=(
                            "Пользователь готов "
                            "доплачивать ради "
                            "других преимуществ."
                        ),
                    )
                )

        # -----------------------------------------------------
        # Duration
        # -----------------------------------------------------

        if (
            ColdStartDimension.DURATION
            in targets
        ):
            delta = (
                _relative_advantage(
                    better=(
                        rejected
                        .duration_minutes
                    ),
                    worse=(
                        selected
                        .duration_minutes
                    ),
                    lower_is_better=True,
                )
            )

            if (
                selected.duration_minutes
                < rejected.duration_minutes
            ):
                strength = (
                    0.30
                    + 0.50
                    * delta
                )

                duration_score += (
                    strength
                )

                signals.append(
                    ColdStartSignal(
                        dimension=(
                            ColdStartDimension
                            .DURATION
                        ),
                        direction=(
                            "prefer_shorter"
                        ),
                        strength=round(
                            strength,
                            4,
                        ),
                        reason=(
                            "Пользователь выбрал "
                            "более быстрый маршрут."
                        ),
                    )
                )

            elif (
                selected.duration_minutes
                > rejected.duration_minutes
            ):
                strength = (
                    0.15
                    + 0.30
                    * delta
                )

                duration_score -= (
                    strength
                )

                signals.append(
                    ColdStartSignal(
                        dimension=(
                            ColdStartDimension
                            .DURATION
                        ),
                        direction=(
                            "accept_longer"
                        ),
                        strength=round(
                            strength,
                            4,
                        ),
                        reason=(
                            "Пользователь готов "
                            "потратить больше времени "
                            "ради других преимуществ."
                        ),
                    )
                )

        # -----------------------------------------------------
        # Transfers
        # -----------------------------------------------------

        if (
            ColdStartDimension.TRANSFERS
            in targets
        ):
            if (
                selected.transfers
                < rejected.transfers
            ):
                difference = (
                    rejected.transfers
                    - selected.transfers
                )

                strength = min(
                    0.85,
                    0.45
                    + 0.20
                    * difference,
                )

                transfers_score += (
                    strength
                )

                signals.append(
                    ColdStartSignal(
                        dimension=(
                            ColdStartDimension
                            .TRANSFERS
                        ),
                        direction=(
                            "prefer_fewer"
                        ),
                        strength=round(
                            strength,
                            4,
                        ),
                        reason=(
                            "Пользователь предпочёл "
                            "вариант с меньшим "
                            "числом пересадок."
                        ),
                    )
                )

            elif (
                selected.transfers
                > rejected.transfers
            ):
                difference = (
                    selected.transfers
                    - rejected.transfers
                )

                strength = min(
                    0.55,
                    0.25
                    + 0.15
                    * difference,
                )

                transfers_score -= (
                    strength
                )

                signals.append(
                    ColdStartSignal(
                        dimension=(
                            ColdStartDimension
                            .TRANSFERS
                        ),
                        direction=(
                            "accept_more"
                        ),
                        strength=round(
                            strength,
                            4,
                        ),
                        reason=(
                            "Пользователь готов "
                            "принимать пересадки "
                            "ради других преимуществ."
                        ),
                    )
                )

        # -----------------------------------------------------
        # Hotel quality
        # -----------------------------------------------------

        if (
            ColdStartDimension
            .HOTEL_QUALITY
            in targets
            and selected.hotel_rating
            is not None
            and rejected.hotel_rating
            is not None
        ):
            if (
                selected.hotel_rating
                > rejected.hotel_rating
            ):
                difference = (
                    selected.hotel_rating
                    - rejected.hotel_rating
                )

                strength = min(
                    0.90,
                    0.35
                    + 0.18
                    * difference,
                )

                hotel_quality_score += (
                    strength
                )

                signals.append(
                    ColdStartSignal(
                        dimension=(
                            ColdStartDimension
                            .HOTEL_QUALITY
                        ),
                        direction=(
                            "prefer_higher"
                        ),
                        strength=round(
                            strength,
                            4,
                        ),
                        reason=(
                            "Пользователь выбрал "
                            "более качественный "
                            "отель."
                        ),
                    )
                )

            elif (
                selected.hotel_rating
                < rejected.hotel_rating
            ):
                difference = (
                    rejected.hotel_rating
                    - selected.hotel_rating
                )

                strength = min(
                    0.60,
                    0.20
                    + 0.12
                    * difference,
                )

                hotel_quality_score -= (
                    strength
                )

                signals.append(
                    ColdStartSignal(
                        dimension=(
                            ColdStartDimension
                            .HOTEL_QUALITY
                        ),
                        direction=(
                            "accept_lower"
                        ),
                        strength=round(
                            strength,
                            4,
                        ),
                        reason=(
                            "Пользователь готов "
                            "выбирать более простой "
                            "отель ради выгоды."
                        ),
                    )
                )

        # -----------------------------------------------------
        # Transport affinity
        # -----------------------------------------------------

        if (
            ColdStartDimension.TRANSPORT
            in targets
            and selected.transport
            != rejected.transport
        ):
            selected_mode = (
                selected
                .transport
                .value
            )

            rejected_mode = (
                rejected
                .transport
                .value
            )

            transport_affinity[
                selected_mode
            ] = (
                transport_affinity.get(
                    selected_mode,
                    0.0,
                )
                + 0.45
            )

            transport_affinity[
                rejected_mode
            ] = (
                transport_affinity.get(
                    rejected_mode,
                    0.0,
                )
                - 0.25
            )

            signals.append(
                ColdStartSignal(
                    dimension=(
                        ColdStartDimension
                        .TRANSPORT
                    ),
                    direction=(
                        f"prefer_{selected_mode}"
                    ),
                    strength=0.45,
                    reason=(
                        "Пользователь предпочёл "
                        f"транспорт: "
                        f"{selected_mode}."
                    ),
                )
            )

    answered = len(
        seen_questions
    )

    total = len(
        active_questions
    )

    minimum = max(
        1,
        min(
            minimum_choices,
            total,
        ),
    )

    completed = (
        answered >= minimum
    )

    confidence = min(
        1.0,
        answered / total,
    )

    # We intentionally start from a small neutral floor.
    #
    # Existing preference ranking expects positive importance
    # weights, while zero means "this factor does not matter".
    #
    # Cold Start should not claim absolute certainty after
    # only a few choices, so all scores remain moderate.
    weights = ColdStartWeights(
        price=(
            _to_weight(
                price_score
            )
        ),
        duration=(
            _to_weight(
                duration_score
            )
        ),
        transfers=(
            _to_weight(
                transfers_score
            )
        ),
        hotel_quality=(
            _to_weight(
                hotel_quality_score
            )
        ),
    )

    normalized_affinity = {
        mode: round(
            _clamp(
                value,
                -2.0,
                2.0,
            ),
            4,
        )
        for mode, value
        in transport_affinity.items()
        if abs(value) > 1e-9
    }

    return ColdStartResult(
        questions_answered=answered,
        total_questions=total,
        completed=completed,
        confidence=round(
            confidence,
            4,
        ),
        weights=weights,
        transport_affinity=(
            normalized_affinity
        ),
        signals=signals,
    )


def _resolve_choice(
    *,
    question: ColdStartQuestion,
    selected_option_id: str,
) -> tuple[
    ColdStartOption,
    ColdStartOption,
]:
    if (
        selected_option_id
        == question.left.id
    ):
        return (
            question.left,
            question.right,
        )

    if (
        selected_option_id
        == question.right.id
    ):
        return (
            question.right,
            question.left,
        )

    raise ValueError(
        "Selected option does not "
        "belong to Cold Start question "
        f"{question.id}"
    )


def _to_weight(
    raw: float,
) -> float:
    """
    Convert directional evidence into the same
    [0, 2] range used by preference weights.

    0.35 is a cautious neutral floor after Cold Start.
    """

    value = (
        0.35
        + raw
    )

    return round(
        _clamp(
            value,
            0.0,
            2.0,
        ),
        4,
    )


def _relative_advantage(
    *,
    better: float,
    worse: float,
    lower_is_better: bool,
) -> float:
    """
    Normalized pair difference in [0, 1].

    Names are intentionally generic because this helper
    only measures magnitude; direction is handled by
    the caller.
    """

    if (
        better == worse
    ):
        return 0.0

    high = max(
        better,
        worse,
    )

    low = min(
        better,
        worse,
    )

    if high <= 0:
        return 0.0

    value = (
        high - low
    ) / high

    if not lower_is_better:
        value = abs(
            value
        )

    return _clamp(
        value,
        0.0,
        1.0,
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


# ============================================================
# Controlled question deck
# ============================================================


def _price_vs_speed() -> (
    ColdStartQuestion
):
    return ColdStartQuestion(
        id="price-vs-speed",
        prompt=(
            "Что выберешь: "
            "сэкономить или доехать быстрее?"
        ),
        left=ColdStartOption(
            id="price-vs-speed:cheap",
            title="Дешевле",
            subtitle=(
                "Автобус · 12 часов"
            ),
            total_price=4_900,
            duration_minutes=720,
            transfers=0,
            transport=(
                TransportMode.BUS
            ),
            hotel_rating=8.0,
        ),
        right=ColdStartOption(
            id="price-vs-speed:fast",
            title="Быстрее",
            subtitle=(
                "Самолёт · 1 ч 50 мин"
            ),
            total_price=10_500,
            duration_minutes=110,
            transfers=0,
            transport=(
                TransportMode.FLIGHT
            ),
            hotel_rating=8.0,
        ),
        targets=[
            ColdStartDimension.PRICE,
            ColdStartDimension.DURATION,
            ColdStartDimension.TRANSPORT,
        ],
    )


def _direct_vs_cheaper() -> (
    ColdStartQuestion
):
    return ColdStartQuestion(
        id="direct-vs-cheaper",
        prompt=(
            "Прямой маршрут или "
            "экономия с пересадкой?"
        ),
        left=ColdStartOption(
            id="direct-vs-cheaper:direct",
            title="Без пересадок",
            subtitle=(
                "Поезд · прямой маршрут"
            ),
            total_price=6_200,
            duration_minutes=540,
            transfers=0,
            transport=(
                TransportMode.TRAIN
            ),
            hotel_rating=8.0,
        ),
        right=ColdStartOption(
            id="direct-vs-cheaper:transfer",
            title="Дешевле",
            subtitle=(
                "Поезд · 1 пересадка"
            ),
            total_price=4_400,
            duration_minutes=620,
            transfers=1,
            transport=(
                TransportMode.TRAIN
            ),
            hotel_rating=8.0,
        ),
        targets=[
            ColdStartDimension.PRICE,
            ColdStartDimension.DURATION,
            ColdStartDimension.TRANSFERS,
        ],
    )


def _train_vs_flight() -> (
    ColdStartQuestion
):
    return ColdStartQuestion(
        id="train-vs-flight",
        prompt=(
            "При почти одинаковой цене "
            "что тебе ближе?"
        ),
        left=ColdStartOption(
            id="train-vs-flight:train",
            title="Поезд",
            subtitle=(
                "Спокойнее и без аэропорта"
            ),
            total_price=7_600,
            duration_minutes=430,
            transfers=0,
            transport=(
                TransportMode.TRAIN
            ),
            hotel_rating=8.0,
        ),
        right=ColdStartOption(
            id="train-vs-flight:flight",
            title="Самолёт",
            subtitle=(
                "Быстрее по маршруту"
            ),
            total_price=7_700,
            duration_minutes=420,
            transfers=0,
            transport=(
                TransportMode.FLIGHT
            ),
            hotel_rating=8.0,
        ),
        targets=[
            ColdStartDimension.TRANSPORT,
        ],
    )


def _hotel_quality_vs_price() -> (
    ColdStartQuestion
):
    return ColdStartQuestion(
        id="hotel-quality-vs-price",
        prompt=(
            "На отеле экономим "
            "или берём комфортнее?"
        ),
        left=ColdStartOption(
            id=(
                "hotel-quality-vs-price:"
                "budget"
            ),
            title="Практичнее",
            subtitle=(
                "Отель 7.2 · дешевле"
            ),
            total_price=13_900,
            duration_minutes=500,
            transfers=0,
            transport=(
                TransportMode.TRAIN
            ),
            hotel_rating=7.2,
        ),
        right=ColdStartOption(
            id=(
                "hotel-quality-vs-price:"
                "comfort"
            ),
            title="Комфортнее",
            subtitle=(
                "Отель 9.1 · дороже"
            ),
            total_price=16_900,
            duration_minutes=500,
            transfers=0,
            transport=(
                TransportMode.TRAIN
            ),
            hotel_rating=9.1,
        ),
        targets=[
            ColdStartDimension.PRICE,
            (
                ColdStartDimension
                .HOTEL_QUALITY
            ),
        ],
    )


def _arrival_time_vs_price() -> (
    ColdStartQuestion
):
    return ColdStartQuestion(
        id="arrival-time-vs-price",
        prompt=(
            "Что важнее: приехать раньше "
            "или заплатить меньше?"
        ),
        left=ColdStartOption(
            id=(
                "arrival-time-vs-price:"
                "earlier"
            ),
            title="Приехать раньше",
            subtitle=(
                "Поезд · 8 ч 40 мин"
            ),
            total_price=8_500,
            duration_minutes=520,
            transfers=0,
            transport=(
                TransportMode.TRAIN
            ),
            hotel_rating=8.0,
        ),
        right=ColdStartOption(
            id=(
                "arrival-time-vs-price:"
                "cheaper"
            ),
            title="Сэкономить",
            subtitle=(
                "Поезд · 11 ч 40 мин"
            ),
            total_price=6_500,
            duration_minutes=700,
            transfers=0,
            transport=(
                TransportMode.TRAIN
            ),
            hotel_rating=8.0,
        ),
        targets=[
            ColdStartDimension.PRICE,
            ColdStartDimension.DURATION,
        ],
    )


def _direct_flight_vs_connection() -> (
    ColdStartQuestion
):
    return ColdStartQuestion(
        id="flight-direct-vs-connection",
        prompt=(
            "Доплатишь за прямой рейс "
            "или возьмёшь пересадку?"
        ),
        left=ColdStartOption(
            id=(
                "flight-direct-vs-connection:"
                "direct"
            ),
            title="Прямой рейс",
            subtitle=(
                "2 часа · без пересадок"
            ),
            total_price=9_800,
            duration_minutes=120,
            transfers=0,
            transport=(
                TransportMode.FLIGHT
            ),
            hotel_rating=8.0,
        ),
        right=ColdStartOption(
            id=(
                "flight-direct-vs-connection:"
                "connection"
            ),
            title="Дешевле",
            subtitle=(
                "3 ч 30 мин · 1 пересадка"
            ),
            total_price=6_900,
            duration_minutes=210,
            transfers=1,
            transport=(
                TransportMode.FLIGHT
            ),
            hotel_rating=8.0,
        ),
        targets=[
            ColdStartDimension.PRICE,
            ColdStartDimension.DURATION,
            ColdStartDimension.TRANSFERS,
        ],
    )