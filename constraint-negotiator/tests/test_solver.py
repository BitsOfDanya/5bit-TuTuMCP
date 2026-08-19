import pytest

from app.models.trip import (
    ConstraintField,
    TransportMode,
    TripSpec,
)
from app.negotiator.solver import ConstraintNegotiator
from app.search.mock import MockJourneyProvider


@pytest.mark.asyncio
async def test_solver_returns_negotiation() -> None:
    trip = TripSpec(
        origin="Москва",
        destination="Казань",
        outbound_date="2026-08-21",
        return_date="2026-08-23",
        outbound_after="19:00:00",
        return_before="22:00:00",
        travelers=2,
        budget=20_000,
        excluded_transport=[TransportMode.BUS],
        preferred_transport=[TransportMode.TRAIN],
        max_transfers=0,
    )

    provider = MockJourneyProvider()

    journeys = await provider.search_candidates(
        trip
    )

    solver = ConstraintNegotiator()

    result = solver.solve(
        trip=trip,
        journeys=journeys,
    )

    assert (
        result.status
        == "negotiation_required"
    )

    assert result.journeys == []

    assert len(
        result.alternatives
    ) == 3

    primary_fields = [
        alternative.changes[0].field
        for alternative
        in result.alternatives
    ]

    assert (
        ConstraintField.BUDGET
        in primary_fields
    )

    assert (
        ConstraintField.OUTBOUND_AFTER
        in primary_fields
    )

    assert (
        ConstraintField.RETURN_BEFORE
        in primary_fields
    )


@pytest.mark.asyncio
async def test_solver_prefers_single_constraint_changes() -> None:
    trip = TripSpec(
        origin="Москва",
        destination="Казань",
        outbound_date="2026-08-21",
        return_date="2026-08-23",
        outbound_after="19:00:00",
        return_before="22:00:00",
        travelers=2,
        budget=20_000,
        excluded_transport=[TransportMode.BUS],
        max_transfers=0,
    )

    provider = MockJourneyProvider()

    journeys = await provider.search_candidates(
        trip
    )

    solver = ConstraintNegotiator()

    result = solver.solve(
        trip=trip,
        journeys=journeys,
    )

    assert (
        result.status
        == "negotiation_required"
    )

    for alternative in result.alternatives:
        assert len(
            alternative.changes
        ) == 1


@pytest.mark.asyncio
async def test_hard_budget_constraint_is_not_relaxed() -> None:
    trip = TripSpec(
        origin="Москва",
        destination="Казань",
        outbound_date="2026-08-21",
        return_date="2026-08-23",
        outbound_after="19:00:00",
        return_before="22:00:00",
        travelers=2,
        budget=20_000,
        excluded_transport=[TransportMode.BUS],
        max_transfers=0,
        hard_constraints={
            ConstraintField.BUDGET,
        },
    )

    provider = MockJourneyProvider()

    journeys = await provider.search_candidates(
        trip
    )

    solver = ConstraintNegotiator()

    result = solver.solve(
        trip=trip,
        journeys=journeys,
    )

    assert (
        result.status
        == "negotiation_required"
    )

    for alternative in result.alternatives:
        for change in alternative.changes:
            assert (
                change.field
                != ConstraintField.BUDGET
            )


@pytest.mark.asyncio
async def test_default_solver_never_returns_multi_constraint_plan() -> None:
    trip = TripSpec(
        origin="Москва",
        destination="Казань",
        outbound_date="2026-08-21",
        return_date="2026-08-23",
        outbound_after="19:00:00",
        return_before="22:00:00",
        travelers=2,
        budget=20_000,
        excluded_transport=[
            TransportMode.BUS
        ],
        max_transfers=0,
    )

    provider = MockJourneyProvider()

    journeys = await provider.search_candidates(
        trip
    )

    solver = ConstraintNegotiator()

    result = solver.solve(
        trip=trip,
        journeys=journeys,
    )

    assert (
        result.status
        == "negotiation_required"
    )

    for alternative in result.alternatives:
        assert len(
            alternative.changes
        ) == 1


@pytest.mark.asyncio
async def test_relaxation_contains_ready_trip_spec() -> None:
    trip = TripSpec(
        origin="Москва",
        destination="Казань",
        outbound_date="2026-08-21",
        return_date="2026-08-23",
        outbound_after="19:00:00",
        return_before="22:00:00",
        travelers=2,
        budget=20_000,
        excluded_transport=[
            TransportMode.BUS
        ],
        max_transfers=0,
    )

    provider = MockJourneyProvider()

    journeys = await provider.search_candidates(
        trip
    )

    solver = ConstraintNegotiator()

    result = solver.solve(
        trip=trip,
        journeys=journeys,
    )

    budget_plan = next(
        plan
        for plan in result.alternatives
        if (
            plan.changes[0].field
            == ConstraintField.BUDGET
        )
    )

    assert (
        budget_plan.new_trip_spec.budget
        == budget_plan.journey.total_price
    )