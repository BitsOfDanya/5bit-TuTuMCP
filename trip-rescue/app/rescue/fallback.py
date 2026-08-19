from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.models.journey import (
    JourneyOption,
)
from app.models.rescue import (
    RescueRelaxation,
)
from app.models.trip import (
    ConstraintField,
    TransportMode,
    TripSpec,
)


@dataclass(
    frozen=True,
    slots=True,
)
class FallbackEvaluation:
    relaxations: tuple[
        RescueRelaxation,
        ...
    ]

    suggested_trip: TripSpec

    score: float


def evaluate_soft_relaxations(
    *,
    trip: TripSpec,
    journey: JourneyOption,
) -> FallbackEvaluation | None:
    """
    Try to make a real Tutu journey feasible by relaxing
    SOFT constraints only.

    Returns None when:
        - structural trip rules are broken;
        - any HARD constraint would have to be violated;
        - the relaxation cannot be represented by TripSpec.

    Returns evaluation with one or more explicit compromises
    otherwise.
    """

    if not _structurally_valid(
        trip=trip,
        journey=journey,
    ):
        return None

    relaxations: list[
        RescueRelaxation
    ] = []

    payload = trip.model_dump(
        mode="json"
    )

    # ---------------------------------------------------------
    # Budget
    # ---------------------------------------------------------

    if (
        trip.budget is not None
        and journey.total_price
        > trip.budget
    ):
        if _is_hard(
            trip,
            ConstraintField.BUDGET,
        ):
            return None

        exceeded = (
            journey.total_price
            - trip.budget
        )

        ratio = (
            exceeded
            / max(
                trip.budget,
                1,
            )
        )

        relaxations.append(
            RescueRelaxation(
                field=ConstraintField.BUDGET,
                title=(
                    "Увеличить бюджет"
                ),
                description=(
                    "Для этого варианта "
                    "нужно увеличить бюджет "
                    f"с {_money(trip.budget)} "
                    f"до "
                    f"{_money(journey.total_price)} "
                    f"(+{_money(exceeded)})."
                ),
                old_value=trip.budget,
                new_value=(
                    journey.total_price
                ),
                magnitude=float(
                    exceeded
                ),
                score=ratio,
            )
        )

        payload[
            "budget"
        ] = journey.total_price

    # ---------------------------------------------------------
    # Outbound time
    # ---------------------------------------------------------

    if trip.outbound_after is not None:
        required = datetime.combine(
            trip.outbound_date,
            trip.outbound_after,
        )

        actual = _naive(
            journey.outbound.departure
        )

        if actual < required:
            if _is_hard(
                trip,
                ConstraintField.OUTBOUND_AFTER,
            ):
                return None

            minutes = int(
                (
                    required
                    - actual
                ).total_seconds()
                // 60
            )

            new_time = (
                actual.time()
                .replace(
                    tzinfo=None
                )
            )

            relaxations.append(
                RescueRelaxation(
                    field=(
                        ConstraintField
                        .OUTBOUND_AFTER
                    ),
                    title=(
                        "Выехать немного раньше"
                    ),
                    description=(
                        "Для этого варианта "
                        f"нужно выехать на "
                        f"{minutes} мин. раньше: "
                        f"{actual:%H:%M} "
                        "вместо "
                        f"{required:%H:%M}."
                    ),
                    old_value=(
                        trip.outbound_after
                        .isoformat()
                    ),
                    new_value=(
                        new_time.isoformat()
                    ),
                    magnitude=float(
                        minutes
                    ),
                    score=(
                        minutes
                        / 120
                    ),
                )
            )

            payload[
                "outbound_after"
            ] = new_time.isoformat()

    # ---------------------------------------------------------
    # Return deadline
    # ---------------------------------------------------------

    if trip.return_before is not None:
        deadline = datetime.combine(
            trip.return_date,
            trip.return_before,
        )

        actual = _naive(
            journey.inbound.arrival
        )

        if actual > deadline:
            if _is_hard(
                trip,
                ConstraintField.RETURN_BEFORE,
            ):
                return None

            # Current TripSpec represents the return deadline
            # as time on return_date.
            #
            # Do not silently move to another calendar day.
            if (
                actual.date()
                != trip.return_date
            ):
                return None

            minutes = int(
                (
                    actual
                    - deadline
                ).total_seconds()
                // 60
            )

            new_time = (
                actual.time()
                .replace(
                    tzinfo=None
                )
            )

            relaxations.append(
                RescueRelaxation(
                    field=(
                        ConstraintField
                        .RETURN_BEFORE
                    ),
                    title=(
                        "Вернуться немного позже"
                    ),
                    description=(
                        "Ближайший вариант "
                        f"прибывает в "
                        f"{actual:%H:%M}, "
                        "то есть на "
                        f"{minutes} мин. позже "
                        "желаемого времени."
                    ),
                    old_value=(
                        trip.return_before
                        .isoformat()
                    ),
                    new_value=(
                        new_time.isoformat()
                    ),
                    magnitude=float(
                        minutes
                    ),
                    score=(
                        minutes
                        / 120
                    ),
                )
            )

            payload[
                "return_before"
            ] = new_time.isoformat()

    # ---------------------------------------------------------
    # Excluded transport
    # ---------------------------------------------------------

    excluded = set(
        trip.excluded_transport
    )

    used_modes = {
        journey.outbound.mode,
        journey.inbound.mode,
    }

    conflicting_modes = (
        excluded
        & used_modes
    )

    if conflicting_modes:
        if _is_hard(
            trip,
            ConstraintField.TRANSPORT,
        ):
            return None

        new_excluded = [
            mode
            for mode
            in trip.excluded_transport
            if mode
            not in conflicting_modes
        ]

        labels = ", ".join(
            _transport_label(
                mode
            )
            for mode
            in sorted(
                conflicting_modes,
                key=lambda item: (
                    item.value
                ),
            )
        )

        relaxations.append(
            RescueRelaxation(
                field=(
                    ConstraintField.TRANSPORT
                ),
                title=(
                    "Разрешить транспорт"
                ),
                description=(
                    "Подходящий вариант "
                    "использует транспорт, "
                    "который был исключён: "
                    f"{labels}."
                ),
                old_value=[
                    mode.value
                    for mode
                    in trip.excluded_transport
                ],
                new_value=[
                    mode.value
                    for mode
                    in new_excluded
                ],
                magnitude=float(
                    len(
                        conflicting_modes
                    )
                ),
                score=(
                    0.8
                    * len(
                        conflicting_modes
                    )
                ),
            )
        )

        payload[
            "excluded_transport"
        ] = [
            mode.value
            for mode
            in new_excluded
        ]

    # ---------------------------------------------------------
    # Transfers
    # ---------------------------------------------------------

    if trip.max_transfers is not None:
        actual_max = max(
            journey.outbound.transfers,
            journey.inbound.transfers,
        )

        if (
            actual_max
            > trip.max_transfers
        ):
            if _is_hard(
                trip,
                ConstraintField.MAX_TRANSFERS,
            ):
                return None

            excess = (
                actual_max
                - trip.max_transfers
            )

            relaxations.append(
                RescueRelaxation(
                    field=(
                        ConstraintField
                        .MAX_TRANSFERS
                    ),
                    title=(
                        "Разрешить больше пересадок"
                    ),
                    description=(
                        "Для этого варианта "
                        f"нужно разрешить "
                        f"до {actual_max} пересадок "
                        "вместо "
                        f"{trip.max_transfers}."
                    ),
                    old_value=(
                        trip.max_transfers
                    ),
                    new_value=actual_max,
                    magnitude=float(
                        excess
                    ),
                    score=(
                        0.7
                        * excess
                    ),
                )
            )

            payload[
                "max_transfers"
            ] = actual_max

    if not relaxations:
        return None

    # ---------------------------------------------------------
    # Combined relaxation penalty
    # ---------------------------------------------------------

    relaxation_score = sum(
        relaxation.score
        for relaxation
        in relaxations
    )

    if len(relaxations) > 1:
        relaxation_score += (
            0.35
            * (
                len(relaxations)
                - 1
            )
        )

    suggested_trip = (
        TripSpec.model_validate(
            payload
        )
    )

    return FallbackEvaluation(
        relaxations=tuple(
            relaxations
        ),
        suggested_trip=(
            suggested_trip
        ),
        score=round(
            relaxation_score,
            6,
        ),
    )


def _structurally_valid(
    *,
    trip: TripSpec,
    journey: JourneyOption,
) -> bool:
    outbound_departure = _naive(
        journey.outbound.departure
    )

    outbound_arrival = _naive(
        journey.outbound.arrival
    )

    inbound_departure = _naive(
        journey.inbound.departure
    )

    inbound_arrival = _naive(
        journey.inbound.arrival
    )

    if (
        outbound_departure.date()
        != trip.outbound_date
    ):
        return False

    if (
        outbound_arrival
        <= outbound_departure
    ):
        return False

    if (
        inbound_arrival
        <= inbound_departure
    ):
        return False

    if (
        inbound_departure
        <= outbound_arrival
    ):
        return False

    # Without a return deadline we preserve the regular
    # "return starts on return_date" semantics.
    if (
        trip.return_before is None
        and inbound_departure.date()
        != trip.return_date
    ):
        return False

    hotel = journey.hotel

    if hotel is not None:
        if (
            hotel.check_in is not None
            and hotel.check_out is not None
            and hotel.check_out
            <= hotel.check_in
        ):
            return False

        if (
            hotel.check_in is not None
            and hotel.check_in
            > inbound_departure.date()
        ):
            return False

    return True


def _is_hard(
    trip: TripSpec,
    field: ConstraintField,
) -> bool:
    return (
        field
        in trip.hard_constraints
    )


def _naive(
    value: datetime,
) -> datetime:
    return value.replace(
        tzinfo=None
    )


def _money(
    value: int,
) -> str:
    return (
        f"{value:,}"
        .replace(",", " ")
        + " ₽"
    )


def _transport_label(
    mode: TransportMode,
) -> str:
    labels = {
        TransportMode.FLIGHT: (
            "самолёт"
        ),
        TransportMode.TRAIN: (
            "поезд"
        ),
        TransportMode.BUS: (
            "автобус"
        ),
        TransportMode.SUBURBAN_TRAIN: (
            "электричка"
        ),
    }

    return labels[
        mode
    ]