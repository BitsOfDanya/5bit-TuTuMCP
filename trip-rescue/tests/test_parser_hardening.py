from __future__ import annotations

from app.ai.parser import (
    ParsedTripUpdate,
    apply_semantic_hardening,
    apply_trip_update,
)
from app.models.rescue import (
    TripField,
)
from app.models.trip import (
    ConstraintField,
    TransportMode,
    TripSpec,
)


def _trip(
    *,
    hard_constraints: (
        set[ConstraintField]
        | None
    ) = None,
    budget: int | None = 22_703,
) -> TripSpec:
    return TripSpec(
        origin="Москва",
        destination="Казань",
        outbound_date="2026-08-21",
        return_date="2026-08-23",
        outbound_after="19:00:00",
        return_before="22:00:00",
        travelers=2,
        budget=budget,
        excluded_transport=[],
        preferred_transport=[],
        max_transfers=None,
        hard_constraints=(
            hard_constraints
            or set()
        ),
    )


def _update(
    *,
    changed_fields: list[
        TripField
    ],
    origin: str | None = None,
    destination: str | None = None,
    outbound_date: str | None = None,
    return_date: str | None = None,
    outbound_after: str | None = None,
    return_before: str | None = None,
    travelers: int | None = None,
    budget: int | None = None,
    excluded_transport: list[
        TransportMode
    ]
    | None = None,
    preferred_transport: list[
        TransportMode
    ]
    | None = None,
    max_transfers: int | None = None,
    hard_constraints: list[
        ConstraintField
    ]
    | None = None,
) -> ParsedTripUpdate:
    return ParsedTripUpdate(
        changed_fields=changed_fields,

        origin=origin,
        destination=destination,

        outbound_date=outbound_date,
        return_date=return_date,

        outbound_after=(
            outbound_after
        ),
        return_before=(
            return_before
        ),

        travelers=travelers,
        budget=budget,

        excluded_transport=(
            excluded_transport
            or []
        ),

        preferred_transport=(
            preferred_transport
            or []
        ),

        max_transfers=(
            max_transfers
        ),

        hard_constraints=(
            hard_constraints
            or []
        ),
    )


def _apply(
    *,
    previous: TripSpec,
    update: ParsedTripUpdate,
    message: str,
) -> TripSpec:
    updated = (
        apply_trip_update(
            previous_trip=previous,
            update=update,
        )
    )

    return (
        apply_semantic_hardening(
            previous_trip=previous,
            updated_trip=updated,
            update=update,
            message=message,
        )
    )


def test_hard_return_and_soft_budget_are_separated() -> None:
    previous = _trip()

    update = _update(
        changed_fields=[
            TripField.RETURN_BEFORE,
            TripField.BUDGET,
            TripField.HARD_CONSTRAINTS,
        ],
        return_before="08:00:00",
        budget=10_000,

        # Simulate the exact bad LLM result:
        # it forgot every hard constraint.
        hard_constraints=[],
    )

    result = _apply(
        previous=previous,
        update=update,
        message=(
            "23 августа мне теперь "
            "обязательно нужно быть "
            "в Москве до 8 утра, "
            "и желательно теперь "
            "уложиться максимум "
            "в 10 тысяч рублей."
        ),
    )

    assert (
        result.return_before
        .isoformat()
        == "08:00:00"
    )

    assert (
        result.budget
        == 10_000
    )

    assert (
        ConstraintField.RETURN_BEFORE
        in result.hard_constraints
    )

    assert (
        ConstraintField.BUDGET
        not in result.hard_constraints
    )


def test_soft_wording_can_remove_previous_hard_return() -> None:
    previous = _trip(
        hard_constraints={
            ConstraintField.RETURN_BEFORE
        }
    )

    update = _update(
        changed_fields=[
            TripField.RETURN_BEFORE
        ],
        return_before="09:00:00",
    )

    result = _apply(
        previous=previous,
        update=update,
        message=(
            "Теперь желательно "
            "вернуться до 9 утра, "
            "но это не обязательно."
        ),
    )

    assert (
        result.return_before
        .isoformat()
        == "09:00:00"
    )

    assert (
        ConstraintField.RETURN_BEFORE
        not in result.hard_constraints
    )


def test_existing_unrelated_hard_constraint_is_preserved() -> None:
    previous = _trip(
        hard_constraints={
            ConstraintField.BUDGET
        }
    )

    update = _update(
        changed_fields=[
            TripField.RETURN_BEFORE,
            TripField.HARD_CONSTRAINTS,
        ],
        return_before="08:00:00",

        # LLM forgot the existing hard budget.
        hard_constraints=[
            ConstraintField.RETURN_BEFORE
        ],
    )

    result = _apply(
        previous=previous,
        update=update,
        message=(
            "Теперь обязательно "
            "надо быть в Москве "
            "до 8 утра."
        ),
    )

    assert (
        ConstraintField.RETURN_BEFORE
        in result.hard_constraints
    )

    assert (
        ConstraintField.BUDGET
        in result.hard_constraints
    )


def test_cleared_constraint_cannot_remain_hard() -> None:
    previous = _trip(
        hard_constraints={
            ConstraintField.BUDGET
        },
        budget=20_000,
    )

    update = _update(
        changed_fields=[
            TripField.BUDGET
        ],
        budget=None,
    )

    result = _apply(
        previous=previous,
        update=update,
        message=(
            "По бюджету ограничений "
            "больше нет."
        ),
    )

    assert (
        result.budget
        is None
    )

    assert (
        ConstraintField.BUDGET
        not in result.hard_constraints
    )


def test_explicit_transport_ban_becomes_hard() -> None:
    previous = _trip()

    update = _update(
        changed_fields=[
            TripField.EXCLUDED_TRANSPORT
        ],
        excluded_transport=[
            TransportMode.BUS
        ],
    )

    result = _apply(
        previous=previous,
        update=update,
        message=(
            "Автобус теперь вообще "
            "исключён."
        ),
    )

    assert (
        TransportMode.BUS
        in result.excluded_transport
    )

    assert (
        ConstraintField.TRANSPORT
        in result.hard_constraints
    )