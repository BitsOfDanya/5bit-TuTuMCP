from app.ai.parser import (
    ParsedTripUpdate,
    apply_trip_update,
)
from app.models.rescue import TripField
from app.models.trip import (
    ConstraintField,
    TransportMode,
    TripSpec,
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


def _empty_update(
    **kwargs,
) -> ParsedTripUpdate:
    payload = {
        "changed_fields": [],
        "origin": None,
        "destination": None,
        "outbound_date": None,
        "return_date": None,
        "outbound_after": None,
        "return_before": None,
        "travelers": None,
        "budget": None,
        "excluded_transport": [],
        "preferred_transport": [],
        "max_transfers": None,
        "hard_constraints": [],
    }

    payload.update(
        kwargs
    )

    return (
        ParsedTripUpdate
        .model_validate(
            payload
        )
    )


def test_update_return_time_only() -> None:
    previous = _trip()

    update = _empty_update(
        changed_fields=[
            TripField.RETURN_BEFORE
        ],
        return_before="08:00:00",
    )

    result = apply_trip_update(
        previous_trip=previous,
        update=update,
    )

    assert (
        result.return_before
        .isoformat()
        == "08:00:00"
    )

    assert (
        result.outbound_after
        == previous.outbound_after
    )

    assert (
        result.budget
        == previous.budget
    )


def test_update_return_time_and_make_hard() -> None:
    previous = _trip()

    update = _empty_update(
        changed_fields=[
            TripField.RETURN_BEFORE,
            TripField.HARD_CONSTRAINTS,
        ],
        return_before="08:00:00",
        hard_constraints=[
            ConstraintField.RETURN_BEFORE
        ],
    )

    result = apply_trip_update(
        previous_trip=previous,
        update=update,
    )

    assert (
        result.return_before
        .isoformat()
        == "08:00:00"
    )

    assert (
        ConstraintField.RETURN_BEFORE
        in result.hard_constraints
    )


def test_clear_budget() -> None:
    previous = _trip()

    update = _empty_update(
        changed_fields=[
            TripField.BUDGET
        ],
        budget=None,
    )

    result = apply_trip_update(
        previous_trip=previous,
        update=update,
    )

    assert result.budget is None


def test_exclude_bus() -> None:
    previous = _trip()

    update = _empty_update(
        changed_fields=[
            TripField.EXCLUDED_TRANSPORT
        ],
        excluded_transport=[
            TransportMode.BUS
        ],
    )

    result = apply_trip_update(
        previous_trip=previous,
        update=update,
    )

    assert (
        result.excluded_transport
        == [
            TransportMode.BUS
        ]
    )


def test_unchanged_fields_are_ignored() -> None:
    previous = _trip()

    update = _empty_update(
        changed_fields=[
            TripField.RETURN_BEFORE
        ],
        return_before="09:00:00",

        # Must be ignored because BUDGET is not
        # in changed_fields.
        budget=999_999,
    )

    result = apply_trip_update(
        previous_trip=previous,
        update=update,
    )

    assert result.budget == 22_703