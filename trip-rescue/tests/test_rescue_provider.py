from __future__ import annotations

import asyncio

from datetime import datetime

from app.models.journey import (
    HotelOption,
    JourneyOption,
    TransportSegment,
)
from app.models.rescue import (
    RescueComponent,
    RescuePlanningResult,
    RescuePlanReason,
    RescueSearchPlan,
)
from app.models.trip import (
    ConstraintField,
    TransportMode,
    TripSpec,
)
from app.tutu.rescue_provider import (
    RescueTutuProvider,
)


class FakeJourneyProvider:
    def __init__(
        self,
        candidates: list[
            JourneyOption
        ],
    ) -> None:
        self.candidates = (
            candidates
        )

        self.calls = 0

    async def search_candidates(
        self,
        trip: TripSpec,
    ) -> list[JourneyOption]:
        self.calls += 1

        return self.candidates


def _trip(
    *,
    return_before: str = "08:00:00",
    budget: int = 22_703,
    hard_constraints: (
        set[ConstraintField]
        | None
    ) = None,
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
            if hard_constraints
            is not None
            else set()
        ),
    )


def _current_journey() -> JourneyOption:
    outbound = TransportSegment(
        id="current-outbound",
        mode=TransportMode.BUS,
        origin="Москва",
        destination="Казань",
        departure=(
            datetime.fromisoformat(
                "2026-08-21T22:45:00+03:00"
            )
        ),
        arrival=(
            datetime.fromisoformat(
                "2026-08-22T08:45:00+03:00"
            )
        ),
        price=5_000,
        transfers=0,
    )

    inbound = TransportSegment(
        id="current-inbound",
        mode=TransportMode.FLIGHT,
        origin="Казань",
        destination="Москва",
        departure=(
            datetime.fromisoformat(
                "2026-08-23T07:05:00+03:00"
            )
        ),
        arrival=(
            datetime.fromisoformat(
                "2026-08-23T08:40:00+03:00"
            )
        ),
        price=14_428,
        transfers=0,
    )

    hotel = HotelOption(
        id="current-hotel",
        name="Мансарда",
        price=3_275,
        check_in="2026-08-22",
        check_out="2026-08-23",
        nights=1,
    )

    return JourneyOption(
        id="current",
        outbound=outbound,
        inbound=inbound,
        hotel=hotel,
        total_price=22_703,
    )


def _external_candidate(
    *,
    inbound_arrival: str,
    inbound_price: int = 12_000,
    hotel_price: int = 2_500,
) -> JourneyOption:
    """
    Deliberately return a completely different journey.

    For inbound-only rescue the external outbound/hotel
    MUST NOT leak into the accepted trip.
    """

    outbound = TransportSegment(
        id="external-outbound",
        mode=TransportMode.FLIGHT,
        origin="Москва",
        destination="Казань",
        departure=(
            datetime.fromisoformat(
                "2026-08-21T20:00:00+03:00"
            )
        ),
        arrival=(
            datetime.fromisoformat(
                "2026-08-21T21:30:00+03:00"
            )
        ),
        price=10_000,
        transfers=0,
    )

    inbound = TransportSegment(
        id="external-inbound",
        mode=TransportMode.FLIGHT,
        origin="Казань",
        destination="Москва",
        departure=(
            datetime.fromisoformat(
                "2026-08-23T05:30:00+03:00"
            )
        ),
        arrival=(
            datetime.fromisoformat(
                inbound_arrival
            )
        ),
        price=inbound_price,
        transfers=0,
    )

    hotel = HotelOption(
        id="external-hotel",
        name="Другой отель",
        price=hotel_price,
        check_in="2026-08-21",
        check_out="2026-08-23",
        nights=2,
    )

    return JourneyOption(
        id="external",
        outbound=outbound,
        inbound=inbound,
        hotel=hotel,
        total_price=(
            outbound.price
            + inbound.price
            + hotel.price
        ),
    )


def _inbound_plan() -> (
    RescuePlanningResult
):
    return RescuePlanningResult(
        status="search_required",
        plans=[
            RescueSearchPlan(
                id="replace-inbound",
                reason=(
                    RescuePlanReason
                    .CONSTRAINT_VIOLATION
                ),
                replace_components=[
                    RescueComponent.INBOUND
                ],
                preserve_components=[
                    RescueComponent.OUTBOUND,
                    RescueComponent.HOTEL,
                ],
                mandatory_components=[
                    RescueComponent.INBOUND
                ],
                budget_target_saving=0,
                score=1.0,
                description=(
                    "Replace inbound"
                ),
            )
        ],
    )


async def _run_inbound_rescue(
    candidate: JourneyOption,
    *,
    trip: TripSpec | None = None,
):
    fake = FakeJourneyProvider(
        [candidate]
    )

    provider = RescueTutuProvider(
        journey_provider=fake
    )

    result = (
        await provider.search_replans(
            trip=(
                trip
                or _trip()
            ),
            current_journey=(
                _current_journey()
            ),
            planning=(
                _inbound_plan()
            ),
        )
    )

    return result, fake


def test_inbound_rescue_preserves_outbound_and_hotel() -> None:
    external = (
        _external_candidate(
            inbound_arrival=(
                "2026-08-23T07:30:00+03:00"
            )
        )
    )

    result, fake = asyncio.run(
        _run_inbound_rescue(
            external
        )
    )

    assert (
        result.status
        == "candidates_found"
    )

    assert fake.calls == 1

    assert len(
        result.candidates
    ) == 1

    candidate = (
        result.candidates[0]
    )

    assert (
        candidate.exact
        is True
    )

    assert (
        candidate.relaxations
        == []
    )

    assert (
        candidate.suggested_trip
        is None
    )

    journey = (
        candidate.journey
    )

    # Preserved outbound.
    assert (
        journey.outbound.id
        == "current-outbound"
    )

    # Preserved hotel.
    assert (
        journey.hotel is not None
    )

    assert (
        journey.hotel.id
        == "current-hotel"
    )

    # Replaced inbound.
    assert (
        journey.inbound.id
        == "external-inbound"
    )

    # 5000 old outbound
    # + 3275 old hotel
    # + 12000 new inbound
    assert (
        journey.total_price
        == 20_275
    )

    assert (
        candidate.replaced_components
        == [
            RescueComponent.INBOUND
        ]
    )

    assert (
        candidate.preserved_components
        == [
            RescueComponent.OUTBOUND,
            RescueComponent.HOTEL,
        ]
    )


def test_soft_invalid_replacement_becomes_negotiation() -> None:
    """
    return_before is SOFT.

    Exact candidate violates 08:00 deadline,
    but instead of deleting the candidate completely
    Rescue must offer the minimum relaxation.
    """

    external = (
        _external_candidate(
            inbound_arrival=(
                "2026-08-23T09:00:00+03:00"
            )
        )
    )

    result, fake = asyncio.run(
        _run_inbound_rescue(
            external
        )
    )

    assert fake.calls == 1

    assert (
        result.status
        == "negotiation_required"
    )

    assert len(
        result.candidates
    ) == 1

    candidate = (
        result.candidates[0]
    )

    assert (
        candidate.exact
        is False
    )

    assert len(
        candidate.relaxations
    ) == 1

    relaxation = (
        candidate.relaxations[0]
    )

    assert (
        relaxation.field
        == ConstraintField.RETURN_BEFORE
    )

    assert (
        relaxation.old_value
        == "08:00:00"
    )

    assert (
        relaxation.new_value
        == "09:00:00"
    )

    assert (
        relaxation.magnitude
        == 60
    )

    assert (
        relaxation.score
        > 0
    )

    assert (
        candidate.suggested_trip
        is not None
    )

    assert (
        candidate
        .suggested_trip
        .return_before
        .isoformat()
        == "09:00:00"
    )

    # Original trip is not mutated.
    assert (
        _trip()
        .return_before
        .isoformat()
        == "08:00:00"
    )

    # Even negotiation still preserves
    # the accepted outbound and hotel.
    assert (
        candidate
        .journey
        .outbound
        .id
        == "current-outbound"
    )

    assert (
        candidate
        .journey
        .hotel
        is not None
    )

    assert (
        candidate
        .journey
        .hotel
        .id
        == "current-hotel"
    )

    assert (
        candidate
        .journey
        .inbound
        .id
        == "external-inbound"
    )


def test_hard_invalid_replacement_is_filtered() -> None:
    """
    return_before is HARD.

    There must be absolutely no negotiation which
    weakens the deadline.
    """

    external = (
        _external_candidate(
            inbound_arrival=(
                "2026-08-23T09:00:00+03:00"
            )
        )
    )

    trip = _trip(
        hard_constraints={
            ConstraintField.RETURN_BEFORE
        }
    )

    result, fake = asyncio.run(
        _run_inbound_rescue(
            external,
            trip=trip,
        )
    )

    assert fake.calls == 1

    assert (
        result.status
        == "no_candidates"
    )

    assert (
        result.candidates
        == []
    )


def test_hard_return_with_soft_budget_relaxes_only_budget() -> None:
    """
    Important combined case.

    The candidate satisfies the HARD return deadline,
    but exceeds a SOFT budget.

    Rescue may negotiate budget,
    but may not touch return_before.
    """

    external = (
        _external_candidate(
            inbound_arrival=(
                "2026-08-23T07:30:00+03:00"
            ),
            inbound_price=18_000,
        )
    )

    trip = _trip(
        budget=20_000,
        hard_constraints={
            ConstraintField.RETURN_BEFORE
        },
    )

    result, fake = asyncio.run(
        _run_inbound_rescue(
            external,
            trip=trip,
        )
    )

    assert fake.calls == 1

    assert (
        result.status
        == "negotiation_required"
    )

    assert len(
        result.candidates
    ) == 1

    candidate = (
        result.candidates[0]
    )

    assert (
        candidate.exact
        is False
    )

    assert len(
        candidate.relaxations
    ) == 1

    relaxation = (
        candidate.relaxations[0]
    )

    assert (
        relaxation.field
        == ConstraintField.BUDGET
    )

    # Preserved:
    # outbound = 5000
    # hotel = 3275
    # new inbound = 18000
    #
    # total = 26275
    assert (
        relaxation.old_value
        == 20_000
    )

    assert (
        relaxation.new_value
        == 26_275
    )

    assert (
        candidate.suggested_trip
        is not None
    )

    assert (
        candidate
        .suggested_trip
        .budget
        == 26_275
    )

    # Hard deadline stays untouched.
    assert (
        candidate
        .suggested_trip
        .return_before
        .isoformat()
        == "08:00:00"
    )

    assert (
        ConstraintField.RETURN_BEFORE
        in candidate
        .suggested_trip
        .hard_constraints
    )


def test_hotel_only_budget_rescue_preserves_transport() -> None:
    current = (
        _current_journey()
    )

    external = (
        _external_candidate(
            inbound_arrival=(
                "2026-08-23T07:30:00+03:00"
            ),
            hotel_price=500,
        )
    )

    fake = FakeJourneyProvider(
        [external]
    )

    provider = RescueTutuProvider(
        journey_provider=fake
    )

    planning = (
        RescuePlanningResult(
            status="search_required",
            plans=[
                RescueSearchPlan(
                    id="replace-hotel",
                    reason=(
                        RescuePlanReason
                        .BUDGET_OPTIMIZATION
                    ),
                    replace_components=[
                        RescueComponent.HOTEL
                    ],
                    preserve_components=[
                        RescueComponent.OUTBOUND,
                        RescueComponent.INBOUND,
                    ],
                    mandatory_components=[],
                    budget_target_saving=(
                        2_703
                    ),
                    score=0.7,
                    description=(
                        "Replace hotel"
                    ),
                )
            ],
        )
    )

    # Current:
    # 5000 + 14428 + 3275 = 22703
    #
    # New:
    # 5000 + 14428 + 500 = 19928
    trip = _trip(
        return_before="22:00:00",
        budget=20_000,
    )

    result = asyncio.run(
        provider.search_replans(
            trip=trip,
            current_journey=current,
            planning=planning,
        )
    )

    assert (
        result.status
        == "candidates_found"
    )

    assert fake.calls == 1

    candidate = (
        result.candidates[0]
    )

    assert (
        candidate.exact
        is True
    )

    journey = (
        candidate.journey
    )

    # Transport stays exactly the same.
    assert (
        journey.outbound.id
        == "current-outbound"
    )

    assert (
        journey.inbound.id
        == "current-inbound"
    )

    # Only hotel changes.
    assert (
        journey.hotel is not None
    )

    assert (
        journey.hotel.id
        == "external-hotel"
    )

    assert (
        journey.total_price
        == 19_928
    )

    assert (
        candidate.price_delta
        == -2_775
    )

    assert (
        candidate.replaced_components
        == [
            RescueComponent.HOTEL
        ]
    )

    assert (
        candidate.preserved_components
        == [
            RescueComponent.OUTBOUND,
            RescueComponent.INBOUND,
        ]
    )


def test_exact_candidate_always_beats_negotiation_candidate() -> None:
    """
    When both exact and relaxed options exist,
    API must return exact candidates.

    Negotiation is only a fallback.
    """

    exact = (
        _external_candidate(
            inbound_arrival=(
                "2026-08-23T07:30:00+03:00"
            ),
            inbound_price=12_000,
        )
    )

    relaxed = (
        _external_candidate(
            inbound_arrival=(
                "2026-08-23T09:00:00+03:00"
            ),
            inbound_price=8_000,
        )
    )

    # Different ID so deduplication does not collapse them.
    relaxed = relaxed.model_copy(
        update={
            "id": "external-relaxed",
            "inbound": (
                relaxed.inbound.model_copy(
                    update={
                        "id": (
                            "external-relaxed-inbound"
                        )
                    }
                )
            ),
        }
    )

    fake = FakeJourneyProvider(
        [
            relaxed,
            exact,
        ]
    )

    provider = RescueTutuProvider(
        journey_provider=fake
    )

    result = asyncio.run(
        provider.search_replans(
            trip=_trip(),
            current_journey=(
                _current_journey()
            ),
            planning=(
                _inbound_plan()
            ),
        )
    )

    assert fake.calls == 1

    assert (
        result.status
        == "candidates_found"
    )

    assert result.candidates

    # Negotiation variants must not leak into the
    # response while an exact solution exists.
    assert all(
        candidate.exact
        is True
        for candidate
        in result.candidates
    )

    assert all(
        candidate.relaxations
        == []
        for candidate
        in result.candidates
    )


def test_multiple_soft_violations_are_exposed_together() -> None:
    """
    A real candidate can require more than one compromise.

    Example:
        return 60 min later
        AND
        budget increase

    Both must be explicit.
    """

    external = (
        _external_candidate(
            inbound_arrival=(
                "2026-08-23T09:00:00+03:00"
            ),
            inbound_price=18_000,
        )
    )

    trip = _trip(
        budget=20_000,
        hard_constraints=set(),
    )

    result, _ = asyncio.run(
        _run_inbound_rescue(
            external,
            trip=trip,
        )
    )

    assert (
        result.status
        == "negotiation_required"
    )

    assert len(
        result.candidates
    ) == 1

    candidate = (
        result.candidates[0]
    )

    assert (
        candidate.exact
        is False
    )

    fields = {
        relaxation.field
        for relaxation
        in candidate.relaxations
    }

    assert fields == {
        ConstraintField.BUDGET,
        ConstraintField.RETURN_BEFORE,
    }

    assert (
        candidate.suggested_trip
        is not None
    )

    assert (
        candidate
        .suggested_trip
        .budget
        == 26_275
    )

    assert (
        candidate
        .suggested_trip
        .return_before
        .isoformat()
        == "09:00:00"
    )