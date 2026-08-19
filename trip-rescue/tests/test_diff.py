from __future__ import annotations

from datetime import (
    time,
)

from app.models.rescue import (
    RescueComponent,
    TripField,
)
from app.models.trip import (
    ConstraintField,
    TransportMode,
    TripSpec,
)
from app.rescue.diff import (
    build_trip_diff,
)


def _base_trip() -> TripSpec:
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


def test_no_changes() -> None:
    previous = _base_trip()

    updated = TripSpec.model_validate(
        previous.model_dump()
    )

    diff = build_trip_diff(
        previous=previous,
        updated=updated,
    )

    assert diff.has_changes is False
    assert diff.changes == []
    assert diff.changed_fields == []
    assert diff.affected_components == []


def test_return_time_only_affects_inbound() -> None:
    previous = _base_trip()

    updated = previous.model_copy(
        update={
            "return_before": time(
                8,
                0,
            )
        }
    )

    diff = build_trip_diff(
        previous=previous,
        updated=updated,
    )

    assert diff.has_changes is True

    assert diff.changed_fields == [
        TripField.RETURN_BEFORE
    ]

    assert diff.affected_components == [
        RescueComponent.INBOUND
    ]

    change = diff.changes[0]

    assert (
        change.old_value
        == "22:00:00"
    )

    assert (
        change.new_value
        == "08:00:00"
    )


def test_budget_change_affects_whole_journey() -> None:
    previous = _base_trip()

    updated = previous.model_copy(
        update={
            "budget": 25_000
        }
    )

    diff = build_trip_diff(
        previous=previous,
        updated=updated,
    )

    assert diff.changed_fields == [
        TripField.BUDGET
    ]

    assert diff.affected_components == [
        RescueComponent.OUTBOUND,
        RescueComponent.HOTEL,
        RescueComponent.INBOUND,
    ]


def test_transport_exclusion_affects_transport_only() -> None:
    previous = _base_trip()

    updated = previous.model_copy(
        update={
            "excluded_transport": [
                TransportMode.BUS
            ]
        }
    )

    diff = build_trip_diff(
        previous=previous,
        updated=updated,
    )

    assert diff.changed_fields == [
        TripField.EXCLUDED_TRANSPORT
    ]

    assert diff.affected_components == [
        RescueComponent.OUTBOUND,
        RescueComponent.INBOUND,
    ]

    assert (
        diff.changes[0].new_value
        == ["bus"]
    )


def test_return_date_affects_hotel_and_inbound() -> None:
    previous = _base_trip()

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

    diff = build_trip_diff(
        previous=previous,
        updated=updated,
    )

    assert diff.changed_fields == [
        TripField.RETURN_DATE
    ]

    assert diff.affected_components == [
        RescueComponent.HOTEL,
        RescueComponent.INBOUND,
    ]


def test_hard_constraint_change_does_not_directly_replace_segment() -> None:
    previous = _base_trip()

    updated = previous.model_copy(
        update={
            "hard_constraints": {
                ConstraintField.RETURN_BEFORE
            }
        }
    )

    diff = build_trip_diff(
        previous=previous,
        updated=updated,
    )

    assert diff.changed_fields == [
        TripField.HARD_CONSTRAINTS
    ]

    assert (
        diff.affected_components
        == []
    )