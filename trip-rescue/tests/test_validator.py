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
    ComponentAction,
    RescueComponent,
)
from app.models.trip import (
    TransportMode,
    TripSpec,
)
from app.rescue.diff import (
    build_trip_diff,
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


def _journey() -> JourneyOption:
    outbound = TransportSegment(
        id="outbound-bus",
        mode=TransportMode.BUS,
        origin=(
            "Международный автовокзал "
            "Саларьево"
        ),
        destination=(
            "Автовокзал Южный"
        ),
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
        carrier="Евротранс",
    )

    inbound = TransportSegment(
        id="inbound-flight",
        mode=TransportMode.FLIGHT,
        origin="Казань, KZN",
        destination=(
            "Москва — Шереметьево"
        ),
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
        carrier="Аэрофлот",
    )

    hotel = HotelOption(
        id="hotel",
        name=(
            "Гостевой Дом Мансарда"
        ),
        price=3_275,
        check_in="2026-08-22",
        check_out="2026-08-23",
        nights=1,
    )

    return JourneyOption(
        id="current-journey",
        outbound=outbound,
        inbound=inbound,
        hotel=hotel,
        total_price=22_703,
    )


def _validation_for(
    *,
    previous: TripSpec,
    updated: TripSpec,
):
    diff = build_trip_diff(
        previous=previous,
        updated=updated,
    )

    return validate_current_journey(
        trip=updated,
        journey=_journey(),
        diff=diff,
    )


def test_same_trip_preserves_everything() -> None:
    previous = _trip()

    updated = TripSpec.model_validate(
        previous.model_dump()
    )

    result = _validation_for(
        previous=previous,
        updated=updated,
    )

    assert (
        result.journey_valid
        is True
    )

    assert (
        result.replace_components
        == []
    )

    assert (
        result.preserved_components
        == [
            RescueComponent.OUTBOUND,
            RescueComponent.HOTEL,
            RescueComponent.INBOUND,
        ]
    )


def test_new_return_deadline_replaces_only_inbound() -> None:
    previous = _trip()

    updated = previous.model_copy(
        update={
            "return_before": time(
                8,
                0,
            )
        }
    )

    result = _validation_for(
        previous=previous,
        updated=updated,
    )

    assert (
        result.journey_valid
        is False
    )

    assert (
        result.preserved_components
        == [
            RescueComponent.OUTBOUND,
            RescueComponent.HOTEL,
        ]
    )

    assert (
        result.replace_components
        == [
            RescueComponent.INBOUND
        ]
    )

    inbound = next(
        item
        for item
        in result.components
        if (
            item.component
            == RescueComponent.INBOUND
        )
    )

    assert (
        inbound.action
        == ComponentAction.REPLACE
    )

    assert (
        inbound.valid
        is False
    )

    assert (
        inbound.reasons[0].code
        == "return_too_late"
    )


def test_return_deadline_that_current_flight_meets_preserves_it() -> None:
    previous = _trip()

    updated = previous.model_copy(
        update={
            "return_before": time(
                9,
                0,
            )
        }
    )

    result = _validation_for(
        previous=previous,
        updated=updated,
    )

    assert (
        result.journey_valid
        is True
    )

    assert (
        result.replace_components
        == []
    )


def test_excluding_bus_replaces_only_outbound() -> None:
    previous = _trip()

    updated = previous.model_copy(
        update={
            "excluded_transport": [
                TransportMode.BUS
            ]
        }
    )

    result = _validation_for(
        previous=previous,
        updated=updated,
    )

    assert (
        result.replace_components
        == [
            RescueComponent.OUTBOUND
        ]
    )

    assert (
        result.preserved_components
        == [
            RescueComponent.HOTEL,
            RescueComponent.INBOUND,
        ]
    )


def test_lower_budget_is_global_violation() -> None:
    previous = _trip()

    updated = previous.model_copy(
        update={
            "budget": 20_000
        }
    )

    result = _validation_for(
        previous=previous,
        updated=updated,
    )

    assert (
        result.journey_valid
        is False
    )

    assert (
        result.budget_violation
        is True
    )

    assert (
        result.budget_exceeded_by
        == 2_703
    )

    # Physical components are still valid.
    # Planner decides what to replace to save money.
    assert (
        result.replace_components
        == []
    )

    assert (
        result.preserved_components
        == [
            RescueComponent.OUTBOUND,
            RescueComponent.HOTEL,
            RescueComponent.INBOUND,
        ]
    )


def test_destination_change_replaces_whole_journey() -> None:
    previous = _trip()

    updated = previous.model_copy(
        update={
            "destination": (
                "Санкт-Петербург"
            )
        }
    )

    result = _validation_for(
        previous=previous,
        updated=updated,
    )

    assert (
        result.replace_components
        == [
            RescueComponent.OUTBOUND,
            RescueComponent.HOTEL,
            RescueComponent.INBOUND,
        ]
    )


def test_return_date_change_replaces_hotel_and_inbound() -> None:
    previous = _trip()

    payload = previous.model_dump(
        mode="json"
    )

    payload[
        "return_date"
    ] = "2026-08-24"

    updated = (
        TripSpec.model_validate(
            payload
        )
    )

    result = _validation_for(
        previous=previous,
        updated=updated,
    )

    assert (
        result.replace_components
        == [
            RescueComponent.HOTEL,
            RescueComponent.INBOUND,
        ]
    )

    assert (
        result.preserved_components
        == [
            RescueComponent.OUTBOUND
        ]
    )


def test_stricter_transfer_limit_replaces_bad_segment() -> None:
    previous = _trip()

    journey = _journey()

    journey.outbound.transfers = 2

    updated = previous.model_copy(
        update={
            "max_transfers": 1
        }
    )

    diff = build_trip_diff(
        previous=previous,
        updated=updated,
    )

    result = validate_current_journey(
        trip=updated,
        journey=journey,
        diff=diff,
    )

    assert (
        result.replace_components
        == [
            RescueComponent.OUTBOUND
        ]
    )

    outbound = result.components[0]

    assert (
        outbound.reasons[0].code
        == "too_many_transfers"
    )


def test_preferred_transport_does_not_force_replacement() -> None:
    previous = _trip()

    updated = previous.model_copy(
        update={
            "preferred_transport": [
                TransportMode.TRAIN
            ]
        }
    )

    result = _validation_for(
        previous=previous,
        updated=updated,
    )

    assert (
        result.journey_valid
        is True
    )

    assert (
        result.replace_components
        == []
    )