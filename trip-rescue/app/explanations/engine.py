from __future__ import annotations

from datetime import datetime

from app.explanations.models import (
    DecisionExplanation,
    ExplanationItem,
    ExplanationType,
)
from app.models.journey import (
    JourneyOption,
)
from app.models.rescue import (
    RescueComponent,
)
from app.models.trip import (
    ConstraintField,
    TripSpec,
)


COMPONENT_LABELS = {
    RescueComponent.OUTBOUND: (
        "дорогу туда"
    ),
    RescueComponent.HOTEL: (
        "отель"
    ),
    RescueComponent.INBOUND: (
        "дорогу обратно"
    ),
}


def build_decision_explanation(
    *,
    trip: TripSpec,
    baseline: JourneyOption,
    candidate: JourneyOption,
    preserved_components: list[
        RescueComponent
    ],
    changed_components: list[
        RescueComponent
    ],
    preference_reasons: (
        list[str]
        | None
    ) = None,
    insight_reasons: (
        list[str]
        | None
    ) = None,
    tradeoff_reasons: (
        list[str]
        | None
    ) = None,
) -> DecisionExplanation:
    """
    Build one unified decision explanation.

    This layer never:
        - changes feasibility;
        - changes candidate score;
        - changes ranking;
        - mutates TripSpec;
        - commits a journey.

    It only explains an already produced decision.
    """

    reasons: list[
        ExplanationItem
    ] = []

    tradeoffs: list[
        ExplanationItem
    ] = []

    _add_preservation_reason(
        reasons=reasons,
        preserved_components=(
            preserved_components
        ),
    )

    _add_hard_constraint_reasons(
        reasons=reasons,
        trip=trip,
        candidate=candidate,
    )

    _add_price_reason(
        reasons=reasons,
        tradeoffs=tradeoffs,
        baseline=baseline,
        candidate=candidate,
    )

    _add_schedule_reason(
        reasons=reasons,
        tradeoffs=tradeoffs,
        baseline=baseline,
        candidate=candidate,
    )

    for text in (
        preference_reasons
        or []
    ):
        clean = text.strip()

        if not clean:
            continue

        reasons.append(
            ExplanationItem(
                type=(
                    ExplanationType
                    .PREFERENCE
                ),
                text=clean,
                positive=True,
            )
        )

    for text in (
        insight_reasons
        or []
    ):
        clean = text.strip()

        if not clean:
            continue

        tradeoffs.append(
            ExplanationItem(
                type=(
                    ExplanationType
                    .INSIGHT
                ),
                text=clean,
                positive=False,
            )
        )

    for text in (
        tradeoff_reasons
        or []
    ):
        clean = text.strip()

        if not clean:
            continue

        tradeoffs.append(
            ExplanationItem(
                type=(
                    ExplanationType
                    .TRADEOFF
                ),
                text=clean,
                positive=False,
            )
        )

    return DecisionExplanation(
        headline=(
            _build_headline(
                changed_components
            )
        ),
        summary=(
            _build_summary(
                baseline=baseline,
                candidate=candidate,
                preserved_components=(
                    preserved_components
                ),
                changed_components=(
                    changed_components
                ),
            )
        ),
        reasons=_deduplicate_items(
            reasons
        ),
        tradeoffs=_deduplicate_items(
            tradeoffs
        ),
        preserved_components=list(
            preserved_components
        ),
        changed_components=list(
            changed_components
        ),
    )


def _add_preservation_reason(
    *,
    reasons: list[
        ExplanationItem
    ],
    preserved_components: list[
        RescueComponent
    ],
) -> None:
    if not preserved_components:
        return

    labels = [
        COMPONENT_LABELS[
            component
        ]
        for component
        in preserved_components
    ]

    reasons.append(
        ExplanationItem(
            type=(
                ExplanationType
                .PRESERVATION
            ),
            text=(
                "Сохраняем "
                f"{_join_labels(labels)}."
            ),
            positive=True,
        )
    )


def _add_hard_constraint_reasons(
    *,
    reasons: list[
        ExplanationItem
    ],
    trip: TripSpec,
    candidate: JourneyOption,
) -> None:
    hard = set(
        trip.hard_constraints
    )

    if (
        ConstraintField.RETURN_BEFORE
        in hard
        and trip.return_before
        is not None
    ):
        arrival = (
            candidate
            .inbound
            .arrival
            .replace(
                tzinfo=None
            )
        )

        deadline = (
            datetime.combine(
                trip.return_date,
                trip.return_before,
            )
        )

        if arrival <= deadline:
            margin = round(
                (
                    deadline
                    - arrival
                ).total_seconds()
                / 60
            )

            if margin > 0:
                text = (
                    "Обязательное время "
                    "возвращения выполнено "
                    f"с запасом "
                    f"{_format_minutes(margin)}."
                )
            else:
                text = (
                    "Обязательное время "
                    "возвращения выполнено "
                    "точно к дедлайну."
                )

            reasons.append(
                ExplanationItem(
                    type=(
                        ExplanationType
                        .CONSTRAINT
                    ),
                    text=text,
                    positive=True,
                )
            )

    if (
        ConstraintField.OUTBOUND_AFTER
        in hard
        and trip.outbound_after
        is not None
    ):
        departure = (
            candidate
            .outbound
            .departure
            .replace(
                tzinfo=None
            )
        )

        boundary = (
            datetime.combine(
                trip.outbound_date,
                trip.outbound_after,
            )
        )

        if departure >= boundary:
            reasons.append(
                ExplanationItem(
                    type=(
                        ExplanationType
                        .CONSTRAINT
                    ),
                    text=(
                        "Обязательное ограничение "
                        "по времени отправления "
                        "соблюдено."
                    ),
                    positive=True,
                )
            )

    if (
        ConstraintField.BUDGET
        in hard
        and trip.budget
        is not None
        and candidate.total_price
        <= trip.budget
    ):
        remaining = (
            trip.budget
            - candidate.total_price
        )

        if remaining > 0:
            text = (
                "Обязательный бюджет "
                "соблюдён, остаётся "
                f"{_rub(remaining)} запаса."
            )
        else:
            text = (
                "Обязательный бюджет "
                "соблюдён точно."
            )

        reasons.append(
            ExplanationItem(
                type=(
                    ExplanationType
                    .CONSTRAINT
                ),
                text=text,
                positive=True,
            )
        )

    if (
        ConstraintField.MAX_TRANSFERS
        in hard
        and trip.max_transfers
        is not None
        and candidate.max_transfers
        <= trip.max_transfers
    ):
        reasons.append(
            ExplanationItem(
                type=(
                    ExplanationType
                    .CONSTRAINT
                ),
                text=(
                    "Обязательное ограничение "
                    "по пересадкам соблюдено."
                ),
                positive=True,
            )
        )

    if (
        ConstraintField.TRANSPORT
        in hard
        and trip.excluded_transport
    ):
        excluded = set(
            trip.excluded_transport
        )

        if not (
            candidate.transport_modes
            & excluded
        ):
            reasons.append(
                ExplanationItem(
                    type=(
                        ExplanationType
                        .CONSTRAINT
                    ),
                    text=(
                        "Запрещённые виды "
                        "транспорта не используются."
                    ),
                    positive=True,
                )
            )


def _add_price_reason(
    *,
    reasons: list[
        ExplanationItem
    ],
    tradeoffs: list[
        ExplanationItem
    ],
    baseline: JourneyOption,
    candidate: JourneyOption,
) -> None:
    delta = (
        candidate.total_price
        - baseline.total_price
    )

    if delta < 0:
        reasons.append(
            ExplanationItem(
                type=(
                    ExplanationType.PRICE
                ),
                text=(
                    "Поездка становится "
                    "дешевле на "
                    f"{_rub(abs(delta))}."
                ),
                positive=True,
            )
        )

        return

    if delta > 0:
        tradeoffs.append(
            ExplanationItem(
                type=(
                    ExplanationType
                    .TRADEOFF
                ),
                text=(
                    "Поездка становится "
                    "дороже на "
                    f"{_rub(delta)}."
                ),
                positive=False,
            )
        )

        return

    reasons.append(
        ExplanationItem(
            type=(
                ExplanationType.PRICE
            ),
            text=(
                "Общая стоимость "
                "не меняется."
            ),
            positive=True,
        )
    )


def _add_schedule_reason(
    *,
    reasons: list[
        ExplanationItem
    ],
    tradeoffs: list[
        ExplanationItem
    ],
    baseline: JourneyOption,
    candidate: JourneyOption,
) -> None:
    old_arrival = (
        baseline
        .inbound
        .arrival
        .replace(
            tzinfo=None
        )
    )

    new_arrival = (
        candidate
        .inbound
        .arrival
        .replace(
            tzinfo=None
        )
    )

    minutes = round(
        (
            new_arrival
            - old_arrival
        ).total_seconds()
        / 60
    )

    if minutes < 0:
        reasons.append(
            ExplanationItem(
                type=(
                    ExplanationType
                    .SCHEDULE
                ),
                text=(
                    "Возвращение будет раньше "
                    "на "
                    f"{_format_minutes(abs(minutes))}."
                ),
                positive=True,
            )
        )

    elif minutes > 0:
        tradeoffs.append(
            ExplanationItem(
                type=(
                    ExplanationType
                    .TRADEOFF
                ),
                text=(
                    "Возвращение будет позже "
                    "на "
                    f"{_format_minutes(minutes)}."
                ),
                positive=False,
            )
        )

    old_outbound = (
        baseline
        .outbound
        .departure
        .replace(
            tzinfo=None
        )
    )

    new_outbound = (
        candidate
        .outbound
        .departure
        .replace(
            tzinfo=None
        )
    )

    outbound_minutes = round(
        (
            new_outbound
            - old_outbound
        ).total_seconds()
        / 60
    )

    if outbound_minutes < 0:
        tradeoffs.append(
            ExplanationItem(
                type=(
                    ExplanationType
                    .TRADEOFF
                ),
                text=(
                    "Выехать туда потребуется "
                    "раньше на "
                    f"{_format_minutes(abs(outbound_minutes))}."
                ),
                positive=False,
            )
        )

    elif outbound_minutes > 0:
        reasons.append(
            ExplanationItem(
                type=(
                    ExplanationType
                    .SCHEDULE
                ),
                text=(
                    "Выехать туда можно позже "
                    "на "
                    f"{_format_minutes(outbound_minutes)}."
                ),
                positive=True,
            )
        )


def _build_headline(
    changed_components: list[
        RescueComponent
    ],
) -> str:
    if not changed_components:
        return (
            "Текущую поездку можно сохранить"
        )

    if len(
        changed_components
    ) == 1:
        component = (
            COMPONENT_LABELS[
                changed_components[0]
            ]
        )

        return (
            f"Меняем только {component}"
        )

    labels = [
        COMPONENT_LABELS[
            component
        ]
        for component
        in changed_components
    ]

    return (
        "Потребуется изменить "
        f"{_join_labels(labels)}"
    )


def _build_summary(
    *,
    baseline: JourneyOption,
    candidate: JourneyOption,
    preserved_components: list[
        RescueComponent
    ],
    changed_components: list[
        RescueComponent
    ],
) -> str:
    parts: list[str] = []

    if preserved_components:
        labels = [
            COMPONENT_LABELS[
                component
            ]
            for component
            in preserved_components
        ]

        parts.append(
            "сохраняем "
            f"{_join_labels(labels)}"
        )

    if changed_components:
        labels = [
            COMPONENT_LABELS[
                component
            ]
            for component
            in changed_components
        ]

        parts.append(
            "меняем "
            f"{_join_labels(labels)}"
        )

    delta = (
        candidate.total_price
        - baseline.total_price
    )

    if delta < 0:
        parts.append(
            "экономия "
            f"{_rub(abs(delta))}"
        )

    elif delta > 0:
        parts.append(
            "доплата "
            f"{_rub(delta)}"
        )

    if not parts:
        return (
            "Сценарий практически "
            "не отличается от текущего."
        )

    result = ". ".join(
        _capitalize_first(
            part
        )
        for part
        in parts
    )

    return (
        result
        + "."
    )


def _deduplicate_items(
    items: list[
        ExplanationItem
    ],
) -> list[
    ExplanationItem
]:
    seen: set[
        tuple[str, str]
    ] = set()

    result: list[
        ExplanationItem
    ] = []

    for item in items:
        signature = (
            item.type.value,
            item.text.strip(),
        )

        if signature in seen:
            continue

        seen.add(
            signature
        )

        result.append(
            item
        )

    return result


def _capitalize_first(
    value: str,
) -> str:
    if not value:
        return value

    return (
        value[0].upper()
        + value[1:]
    )


def _join_labels(
    values: list[str],
) -> str:
    if not values:
        return ""

    if len(values) == 1:
        return values[0]

    return (
        ", ".join(
            values[:-1]
        )
        + " и "
        + values[-1]
    )


def _rub(
    value: int,
) -> str:
    return (
        f"{value:,}"
        .replace(
            ",",
            " ",
        )
        + " ₽"
    )


def _format_minutes(
    minutes: int,
) -> str:
    hours, rest = divmod(
        minutes,
        60,
    )

    if hours and rest:
        return (
            f"{hours} ч {rest} мин"
        )

    if hours:
        return (
            f"{hours} ч"
        )

    return (
        f"{rest} мин"
    )