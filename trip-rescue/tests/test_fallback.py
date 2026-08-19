from __future__ import annotations

from datetime import datetime

from app.models.journey import (
    JourneyOption,
    TransportSegment,
)
from app.models.trip import (
    ConstraintField,
    TransportMode,
    TripSpec,
)
from app.rescue.fallback import (
    evaluate_soft_relaxations,
)


def _trip(
    *,
    budget: int | None = 20_000,
    return_before: str | None = "08:00:00",
    hard_constraints=None,
) -> TripSpec:
    return TripSpec(
        origin="Москва",
        destination="Казань",
        outbound_date="2026-08-21",
        return_date="2026-08-23",
        outbound_after="19:00:00",
        return_before=return_before,
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


def _segment(
    *,
    segment_id: str,
    departure: str,
    arrival: str,
    price: int,
    mode: TransportMode = (
        TransportMode.BUS
    ),
    transfers: int = 0,
) -> TransportSegment:
    return TransportSegment(
        id=segment_id,
        mode=mode,
        origin="A",
        destination="B",
        departure=(
            datetime.fromisoformat(
                departure
            )
        ),
        arrival=(
            datetime.fromisoformat(
                arrival
            )
        ),
        price=price,
        transfers=transfers,
    )


def _journey(
    *,
    inbound_arrival: str = (
        "2026-08-23T07:00:00+03:00"
    ),
    inbound_price: int = 18_000,
) -> JourneyOption:
    outbound = _segment(
        segment_id="out",
        departure=(
            "2026-08-21T22:45:00+03:00"
        ),
        arrival=(
            "2026-08-22T08:45:00+03:00"
        ),
        price=5_000,
    )

    inbound = _segment(
        segment_id="back",
        departure=(
            "2026-08-22T19:00:00+03:00"
        ),
        arrival=(
            inbound_arrival
        ),
        price=inbound_price,
    )

    return JourneyOption(
        id="journey",
        outbound=outbound,
        inbound=inbound,
        hotel=None,
        total_price=(
            outbound.price
            + inbound.price
        ),
    )


def test_soft_budget_can_be_relaxed() -> None:
    trip = _trip(
        budget=20_000
    )

    journey = _journey(
        inbound_price=18_000
    )

    result = (
        evaluate_soft_relaxations(
            trip=trip,
            journey=journey,
        )
    )

    assert result is not None

    assert len(
        result.relaxations
    ) == 1

    relaxation = (
        result.relaxations[0]
    )

    assert (
        relaxation.field
        == ConstraintField.BUDGET
    )

    assert (
        relaxation.old_value
        == 20_000
    )

    assert (
        relaxation.new_value
        == 23_000
    )

    assert (
        result.suggested_trip
        .budget
        == 23_000
    )


def test_hard_budget_can_never_be_relaxed() -> None:
    trip = _trip(
        budget=20_000,
        hard_constraints={
            ConstraintField.BUDGET
        },
    )

    journey = _journey(
        inbound_price=18_000
    )

    result = (
        evaluate_soft_relaxations(
            trip=trip,
            journey=journey,
        )
    )

    assert result is None


def test_hard_return_deadline_rejects_late_candidate() -> None:
    trip = _trip(
        budget=None,
        hard_constraints={
            ConstraintField.RETURN_BEFORE
        },
    )

    journey = _journey(
        inbound_arrival=(
            "2026-08-23T08:40:00+03:00"
        ),
        inbound_price=10_000,
    )

    result = (
        evaluate_soft_relaxations(
            trip=trip,
            journey=journey,
        )
    )

    assert result is None


def test_soft_return_deadline_can_be_relaxed() -> None:
    trip = _trip(
        budget=None,
        hard_constraints=set(),
    )

    journey = _journey(
        inbound_arrival=(
            "2026-08-23T08:40:00+03:00"
        ),
        inbound_price=10_000,
    )

    result = (
        evaluate_soft_relaxations(
            trip=trip,
            journey=journey,
        )
    )

    assert result is not None

    relaxation = (
        result.relaxations[0]
    )

    assert (
        relaxation.field
        == ConstraintField.RETURN_BEFORE
    )

    assert (
        relaxation.magnitude
        == 40
    )

    assert (
        result.suggested_trip
        .return_before
        .isoformat()
        == "08:40:00"
    )


def test_hard_return_and_soft_budget_only_relaxes_budget() -> None:
    trip = _trip(
        budget=20_000,
        hard_constraints={
            ConstraintField.RETURN_BEFORE
        },
    )

    # Arrives BEFORE the hard deadline,
    # but costs too much.
    journey = _journey(
        inbound_arrival=(
            "2026-08-23T07:00:00+03:00"
        ),
        inbound_price=18_000,
    )

    result = (
        evaluate_soft_relaxations(
            trip=trip,
            journey=journey,
        )
    )

    assert result is not None

    assert [
        relaxation.field
        for relaxation
        in result.relaxations
    ] == [
        ConstraintField.BUDGET
    ]


def test_multiple_soft_relaxations_get_combination_penalty() -> None:
    trip = _trip(
        budget=20_000,
        hard_constraints=set(),
    )

    journey = _journey(
        inbound_arrival=(
            "2026-08-23T08:40:00+03:00"
        ),
        inbound_price=18_000,
    )

    result = (
        evaluate_soft_relaxations(
            trip=trip,
            journey=journey,
        )
    )

    assert result is not None

    fields = {
        relaxation.field
        for relaxation
        in result.relaxations
    }

    assert fields == {
        ConstraintField.BUDGET,
        ConstraintField.RETURN_BEFORE,
    }

    individual_score = sum(
        relaxation.score
        for relaxation
        in result.relaxations
    )

    assert (
        result.score
        > individual_score
    )