from datetime import datetime

import pytest

from app.models.journey import (
    HotelOption,
    JourneyOption,
    TransportSegment,
)
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
        excluded_transport=[
            TransportMode.BUS,
        ],
        preferred_transport=[
            TransportMode.TRAIN,
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

    assert result.journeys == []

    assert len(
        result.alternatives
    ) == 3

    primary_fields = {
        alternative.changes[0].field
        for alternative in result.alternatives
    }

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
        excluded_transport=[
            TransportMode.BUS,
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

        assert (
            alternative.kind
            == "single"
        )


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
        excluded_transport=[
            TransportMode.BUS,
        ],
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
            TransportMode.BUS,
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


@pytest.mark.asyncio
async def test_single_relaxations_have_single_kind() -> None:
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
            TransportMode.BUS,
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

    for plan in result.alternatives:
        if len(plan.changes) == 1:
            assert (
                plan.kind
                == "single"
            )


@pytest.mark.asyncio
async def test_combination_fallback_can_be_disabled() -> None:
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
            TransportMode.BUS,
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
        allow_combination_fallback=False,
    )

    assert all(
        plan.kind == "single"
        for plan in result.alternatives
    )


def test_solver_returns_minimal_two_constraint_combination() -> None:
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
            TransportMode.BUS,
        ],
        max_transfers=0,
    )

    outbound = TransportSegment(
        id="bus-out",
        mode=TransportMode.BUS,
        origin="Москва",
        destination="Казань",
        departure=datetime.fromisoformat(
            "2026-08-21T22:45:00+03:00"
        ),
        arrival=datetime.fromisoformat(
            "2026-08-22T08:45:00+03:00"
        ),
        price=5_000,
    )

    inbound = TransportSegment(
        id="flight-back",
        mode=TransportMode.FLIGHT,
        origin="Казань",
        destination="Москва",
        departure=datetime.fromisoformat(
            "2026-08-23T07:05:00+03:00"
        ),
        arrival=datetime.fromisoformat(
            "2026-08-23T08:40:00+03:00"
        ),
        price=14_428,
    )

    hotel = HotelOption(
        id="hotel",
        name="Test Hotel",
        price=3_569,
    )

    journey = JourneyOption(
        id="bus-budget-combo",
        outbound=outbound,
        inbound=inbound,
        hotel=hotel,
        total_price=22_997,
    )

    solver = ConstraintNegotiator()

    result = solver.solve(
        trip=trip,
        journeys=[
            journey,
        ],
    )

    assert (
        result.status
        == "negotiation_required"
    )

    assert len(
        result.alternatives
    ) == 1

    plan = result.alternatives[0]

    assert (
        plan.kind
        == "combination"
    )

    assert len(
        plan.changes
    ) == 2

    fields = {
        change.field
        for change in plan.changes
    }

    assert fields == {
        ConstraintField.BUDGET,
        ConstraintField.TRANSPORT,
    }

    assert (
        plan.new_trip_spec.budget
        == 22_997
    )

    assert (
        TransportMode.BUS
        not in plan
        .new_trip_spec
        .excluded_transport
    )


def test_three_constraint_plan_is_not_returned() -> None:
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
            TransportMode.BUS,
        ],
        max_transfers=0,
    )

    outbound = TransportSegment(
        id="bad-out",
        mode=TransportMode.BUS,
        origin="Москва",
        destination="Казань",
        departure=datetime.fromisoformat(
            "2026-08-21T18:00:00+03:00"
        ),
        arrival=datetime.fromisoformat(
            "2026-08-22T08:00:00+03:00"
        ),
        price=15_000,
    )

    inbound = TransportSegment(
        id="bad-back",
        mode=TransportMode.FLIGHT,
        origin="Казань",
        destination="Москва",
        departure=datetime.fromisoformat(
            "2026-08-23T22:00:00+03:00"
        ),
        arrival=datetime.fromisoformat(
            "2026-08-24T00:00:00+03:00"
        ),
        price=15_000,
    )

    journey = JourneyOption(
        id="three-changes",
        outbound=outbound,
        inbound=inbound,
        hotel=None,
        total_price=30_000,
    )

    solver = ConstraintNegotiator()

    result = solver.solve(
        trip=trip,
        journeys=[
            journey,
        ],
    )

    assert (
        result.status
        == "no_options"
    )

    assert (
        result.alternatives
        == []
    )

def test_dominated_combination_is_removed_by_single_plan() -> None:
    trip = TripSpec(
        origin="Москва",
        destination="Казань",
        outbound_date="2026-08-21",
        return_date="2026-08-23",
        outbound_after="19:00:00",
        return_before="22:00:00",
        travelers=2,
        budget=20_000,
        max_transfers=0,
    )

    single_outbound = TransportSegment(
        id="single-out",
        mode=TransportMode.FLIGHT,
        origin="Москва",
        destination="Казань",
        departure=datetime.fromisoformat(
            "2026-08-21T21:00:00+03:00"
        ),
        arrival=datetime.fromisoformat(
            "2026-08-21T22:30:00+03:00"
        ),
        price=12_000,
    )

    single_inbound = TransportSegment(
        id="single-back",
        mode=TransportMode.FLIGHT,
        origin="Казань",
        destination="Москва",
        departure=datetime.fromisoformat(
            "2026-08-23T18:00:00+03:00"
        ),
        arrival=datetime.fromisoformat(
            "2026-08-23T20:00:00+03:00"
        ),
        price=10_000,
    )

    single = JourneyOption(
        id="single-budget",
        outbound=single_outbound,
        inbound=single_inbound,
        hotel=None,
        total_price=22_000,
    )

    combo_outbound = TransportSegment(
        id="combo-out",
        mode=TransportMode.FLIGHT,
        origin="Москва",
        destination="Казань",
        departure=datetime.fromisoformat(
            "2026-08-21T21:00:00+03:00"
        ),
        arrival=datetime.fromisoformat(
            "2026-08-21T22:30:00+03:00"
        ),
        price=13_000,
    )

    combo_inbound = TransportSegment(
        id="combo-back",
        mode=TransportMode.FLIGHT,
        origin="Казань",
        destination="Москва",
        departure=datetime.fromisoformat(
            "2026-08-23T21:00:00+03:00"
        ),
        arrival=datetime.fromisoformat(
            "2026-08-23T22:25:00+03:00"
        ),
        price=12_000,
    )

    combo = JourneyOption(
        id="budget-time-combo",
        outbound=combo_outbound,
        inbound=combo_inbound,
        hotel=None,
        total_price=25_000,
    )

    solver = ConstraintNegotiator()

    result = solver.solve(
        trip=trip,
        journeys=[
            single,
            combo,
        ],
    )

    assert (
        result.status
        == "negotiation_required"
    )

    assert len(
        result.alternatives
    ) == 1

    assert (
        result.alternatives[0].kind
        == "single"
    )

    assert (
        result.alternatives[0]
        .changes[0]
        .field
        == ConstraintField.BUDGET
    )

    assert (
        result.alternatives[0]
        .journey
        .id
        == "single-budget"
    )