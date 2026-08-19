from datetime import datetime

import pytest

from app.models.journey import (
    JourneyOption,
    TransportSegment,
)
from app.models.trip import (
    ConstraintField,
    TransportMode,
    TripSpec,
)
from app.negotiator.feasibility import evaluate_constraints
from app.search.mock import MockJourneyProvider


@pytest.mark.asyncio
async def test_timezone_aware_constraints_are_compared_as_local_wall_clock() -> None:
    trip = TripSpec(
        origin="Москва",
        destination="Казань",
        outbound_date="2026-08-21",
        return_date="2026-08-23",
        outbound_after="19:00:00+03:00",
        return_before="22:00:00+03:00",
        travelers=1,
        budget=30_000,
    )
    journeys = await MockJourneyProvider().search_candidates(trip)

    violations = evaluate_constraints(trip=trip, journey=journeys[0])

    assert isinstance(violations, list)


@pytest.mark.asyncio
async def test_budget_violation() -> None:
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
    journeys = await provider.search_candidates(trip)

    journey = next(
        item
        for item in journeys
        if item.id == "exact-expensive"
    )

    violations = evaluate_constraints(
        trip=trip,
        journey=journey,
    )

    assert len(violations) == 1

    change = violations[0]

    assert change.field == ConstraintField.BUDGET
    assert change.old_value == 20_000
    assert change.new_value == 22_000
    assert change.magnitude == 2_000


@pytest.mark.asyncio
async def test_departure_violation() -> None:
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
    journeys = await provider.search_candidates(trip)

    journey = next(
        item
        for item in journeys
        if item.id == "leave-earlier"
    )

    violations = evaluate_constraints(
        trip=trip,
        journey=journey,
    )

    assert len(violations) == 1

    change = violations[0]

    assert change.field == ConstraintField.OUTBOUND_AFTER
    assert change.magnitude == 45
    assert change.new_value == "2026-08-21 18:15"


@pytest.mark.asyncio
async def test_return_violation() -> None:
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
    journeys = await provider.search_candidates(trip)

    journey = next(
        item
        for item in journeys
        if item.id == "return-later"
    )

    violations = evaluate_constraints(
        trip=trip,
        journey=journey,
    )

    assert len(violations) == 1

    change = violations[0]

    assert change.field == ConstraintField.RETURN_BEFORE
    assert change.magnitude == 75
    assert change.new_value == "2026-08-23 23:15"


@pytest.mark.asyncio
async def test_excluded_transport_violation() -> None:
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
    journeys = await provider.search_candidates(trip)

    journey = next(
        item
        for item in journeys
        if item.id == "cheap-bus"
    )

    violations = evaluate_constraints(
        trip=trip,
        journey=journey,
    )

    assert len(violations) == 1

    change = violations[0]

    assert change.field == ConstraintField.TRANSPORT


def test_return_next_day_is_violation() -> None:
    trip = TripSpec(
        origin="Москва",
        destination="Казань",
        outbound_date="2026-08-21",
        return_date="2026-08-23",
        outbound_after="19:00:00",
        return_before="22:00:00",
        travelers=2,
        budget=50_000,
    )

    outbound = TransportSegment(
        id="out",
        mode=TransportMode.TRAIN,
        origin="Москва",
        destination="Казань",
        departure=datetime.fromisoformat(
            "2026-08-21T20:00:00+03:00"
        ),
        arrival=datetime.fromisoformat(
            "2026-08-22T08:00:00+03:00"
        ),
        price=5_000,
    )

    inbound = TransportSegment(
        id="back",
        mode=TransportMode.BUS,
        origin="Казань",
        destination="Москва",
        departure=datetime.fromisoformat(
            "2026-08-23T19:00:00+03:00"
        ),
        arrival=datetime.fromisoformat(
            "2026-08-24T07:00:00+03:00"
        ),
        price=6_000,
    )

    journey = JourneyOption(
        id="next-day-return",
        outbound=outbound,
        inbound=inbound,
        total_price=11_000,
    )

    violations = evaluate_constraints(
        trip=trip,
        journey=journey,
    )

    return_violation = next(
        item
        for item in violations
        if item.field == ConstraintField.RETURN_BEFORE
    )

    assert return_violation.magnitude == 540
    assert return_violation.old_value == "2026-08-23 22:00"
    assert return_violation.new_value == "2026-08-24 07:00"
