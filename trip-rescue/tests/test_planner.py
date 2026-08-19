from __future__ import annotations

from datetime import (
    datetime,
    time,
)

from app.models.journey import (
    HotelOption,
    JourneyOption,
    TransportSegment,
)
from app.models.rescue import (
    RescueComponent,
    RescuePlanReason,
)
from app.models.trip import (
    TransportMode,
    TripSpec,
)
from app.rescue.diff import (
    build_trip_diff,
)
from app.rescue.planner import (
    build_rescue_search_plans,
)
from app.rescue.validator import (
    validate_current_journey,
)


def _trip() -> TripSpec:
    return TripSpec(
        origin="Москва",
        destination="Казань",
        outbound_date="2026-08-21",
        return_date="2026-08-23",
        outbound_after="19:00:00",
        return_before="22:00:00",
        travelers=2,
        budget=22_703,
        excluded_transport=[],
        preferred_transport=[],
        max_transfers=None,
        hard_constraints=set(),
    )


def _journey(
    *,
    with_hotel: bool = True,
) -> JourneyOption:

    outbound = TransportSegment(
        id="outbound",
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
        id="inbound",
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

    hotel = None

    if with_hotel:
        hotel = HotelOption(
            id="hotel",
            name="Мансарда",
            price=3_275,
            check_in="2026-08-22",
            check_out="2026-08-23",
            nights=1,
        )

    total_price = (
        outbound.price
        + inbound.price
        + (
            hotel.price
            if hotel is not None
            else 0
        )
    )

    return JourneyOption(
        id="journey",
        outbound=outbound,
        inbound=inbound,
        hotel=hotel,
        total_price=total_price,
    )


def _plan(
    *,
    previous: TripSpec,
    updated: TripSpec,
    journey: JourneyOption | None = None,
):
    active_journey = (
        journey
        or _journey()
    )

    diff = build_trip_diff(
        previous=previous,
        updated=updated,
    )

    validation = (
        validate_current_journey(
            trip=updated,
            journey=active_journey,
            diff=diff,
        )
    )

    return (
        build_rescue_search_plans(
            trip=updated,
            journey=active_journey,
            validation=validation,
        )
    )


def test_valid_journey_requires_no_search() -> None:
    previous = _trip()

    updated = TripSpec.model_validate(
        previous.model_dump()
    )

    result = _plan(
        previous=previous,
        updated=updated,
    )

    assert (
        result.status
        == "no_change"
    )

    assert result.plans == []


def test_return_deadline_searches_only_inbound() -> None:
    previous = _trip()

    updated = previous.model_copy(
        update={
            "return_before": time(
                8,
                0,
            )
        }
    )

    result = _plan(
        previous=previous,
        updated=updated,
    )

    assert (
        result.status
        == "search_required"
    )

    assert len(
        result.plans
    ) == 1

    plan = result.plans[0]

    assert (
        plan.replace_components
        == [
            RescueComponent.INBOUND
        ]
    )

    assert (
        plan.preserve_components
        == [
            RescueComponent.OUTBOUND,
            RescueComponent.HOTEL,
        ]
    )

    assert (
        plan.reason
        == RescuePlanReason
        .CONSTRAINT_VIOLATION
    )


def test_budget_only_generates_minimal_search_options() -> None:
    previous = _trip()

    updated = previous.model_copy(
        update={
            "budget": 20_000
        }
    )

    result = _plan(
        previous=previous,
        updated=updated,
    )

    assert (
        result.status
        == "search_required"
    )

    assert result.plans

    # Hotel is the least disruptive thing
    # to try replacing first.
    assert (
        result.plans[0]
        .replace_components
        == [
            RescueComponent.HOTEL
        ]
    )

    assert all(
        len(
            plan.replace_components
        )
        <= 2
        for plan
        in result.plans
    )

    assert all(
        plan.budget_target_saving
        == 2_703
        for plan
        in result.plans
    )


def test_budget_search_never_uses_missing_hotel() -> None:
    previous = _trip()

    journey = _journey(
        with_hotel=False
    )

    previous = previous.model_copy(
        update={
            "budget": (
                journey.total_price
            )
        }
    )

    updated = previous.model_copy(
        update={
            "budget": (
                journey.total_price
                - 1_000
            )
        }
    )

    result = _plan(
        previous=previous,
        updated=updated,
        journey=journey,
    )

    assert result.plans

    assert all(
        RescueComponent.HOTEL
        not in plan.replace_components
        for plan
        in result.plans
    )


def test_destination_change_rebuilds_whole_journey() -> None:
    previous = _trip()

    updated = previous.model_copy(
        update={
            "destination": (
                "Санкт-Петербург"
            )
        }
    )

    result = _plan(
        previous=previous,
        updated=updated,
    )

    assert len(
        result.plans
    ) == 1

    assert (
        result.plans[0]
        .replace_components
        == [
            RescueComponent.OUTBOUND,
            RescueComponent.HOTEL,
            RescueComponent.INBOUND,
        ]
    )

    assert (
        result.plans[0]
        .preserve_components
        == []
    )


def test_mixed_problem_never_drops_mandatory_component() -> None:
    previous = _trip()

    # Current inbound arrives at 08:40.
    # New requirement is 08:00.
    #
    # At the same time budget is reduced.
    updated = previous.model_copy(
        update={
            "return_before": time(
                8,
                0,
            ),
            "budget": 20_000,
        }
    )

    result = _plan(
        previous=previous,
        updated=updated,
    )

    assert result.plans

    assert all(
        RescueComponent.INBOUND
        in plan.replace_components
        for plan
        in result.plans
    )

    assert (
        result.plans[0]
        .replace_components
        == [
            RescueComponent.INBOUND
        ]
    )

    assert (
        result.plans[0].reason
        == RescuePlanReason.MIXED
    )