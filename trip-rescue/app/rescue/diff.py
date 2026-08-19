from __future__ import annotations

from typing import Any

from app.models.rescue import (
    RescueComponent,
    TripDiff,
    TripField,
    TripFieldChange,
)
from app.models.trip import TripSpec


FIELD_COMPONENTS: dict[
    TripField,
    tuple[RescueComponent, ...],
] = {
    TripField.ORIGIN: (
        RescueComponent.OUTBOUND,
        RescueComponent.INBOUND,
    ),

    TripField.DESTINATION: (
        RescueComponent.OUTBOUND,
        RescueComponent.HOTEL,
        RescueComponent.INBOUND,
    ),

    TripField.OUTBOUND_DATE: (
        RescueComponent.OUTBOUND,
        RescueComponent.HOTEL,
    ),

    TripField.RETURN_DATE: (
        RescueComponent.HOTEL,
        RescueComponent.INBOUND,
    ),

    TripField.OUTBOUND_AFTER: (
        RescueComponent.OUTBOUND,
    ),

    TripField.RETURN_BEFORE: (
        RescueComponent.INBOUND,
    ),

    TripField.TRAVELERS: (
        RescueComponent.OUTBOUND,
        RescueComponent.HOTEL,
        RescueComponent.INBOUND,
    ),

    TripField.BUDGET: (
        RescueComponent.OUTBOUND,
        RescueComponent.HOTEL,
        RescueComponent.INBOUND,
    ),

    TripField.EXCLUDED_TRANSPORT: (
        RescueComponent.OUTBOUND,
        RescueComponent.INBOUND,
    ),

    TripField.PREFERRED_TRANSPORT: (
        RescueComponent.OUTBOUND,
        RescueComponent.INBOUND,
    ),

    TripField.MAX_TRANSFERS: (
        RescueComponent.OUTBOUND,
        RescueComponent.INBOUND,
    ),

    # Changing which constraints are "hard"
    # changes policy, but does not directly
    # invalidate a specific physical segment.
    TripField.HARD_CONSTRAINTS: (),
}


FIELD_ORDER: tuple[
    TripField,
    ...,
] = (
    TripField.ORIGIN,
    TripField.DESTINATION,
    TripField.OUTBOUND_DATE,
    TripField.RETURN_DATE,
    TripField.OUTBOUND_AFTER,
    TripField.RETURN_BEFORE,
    TripField.TRAVELERS,
    TripField.BUDGET,
    TripField.EXCLUDED_TRANSPORT,
    TripField.PREFERRED_TRANSPORT,
    TripField.MAX_TRANSFERS,
    TripField.HARD_CONSTRAINTS,
)


COMPONENT_ORDER: tuple[
    RescueComponent,
    ...,
] = (
    RescueComponent.OUTBOUND,
    RescueComponent.HOTEL,
    RescueComponent.INBOUND,
)


def build_trip_diff(
    *,
    previous: TripSpec,
    updated: TripSpec,
) -> TripDiff:

    changes: list[
        TripFieldChange
    ] = []

    affected: set[
        RescueComponent
    ] = set()

    for field in FIELD_ORDER:
        old_value = getattr(
            previous,
            field.value,
        )

        new_value = getattr(
            updated,
            field.value,
        )

        if _values_equal(
            field=field,
            left=old_value,
            right=new_value,
        ):
            continue

        components = list(
            FIELD_COMPONENTS[field]
        )

        affected.update(
            components
        )

        changes.append(
            TripFieldChange(
                field=field,
                old_value=(
                    _serialize_value(
                        field=field,
                        value=old_value,
                    )
                ),
                new_value=(
                    _serialize_value(
                        field=field,
                        value=new_value,
                    )
                ),
                affected_components=(
                    components
                ),
            )
        )

    changed_fields = [
        change.field
        for change
        in changes
    ]

    affected_components = [
        component
        for component
        in COMPONENT_ORDER
        if component in affected
    ]

    return TripDiff(
        has_changes=bool(
            changes
        ),
        changes=changes,
        changed_fields=(
            changed_fields
        ),
        affected_components=(
            affected_components
        ),
    )


def _values_equal(
    *,
    field: TripField,
    left: Any,
    right: Any,
) -> bool:

    if field in {
        TripField.EXCLUDED_TRANSPORT,
        TripField.PREFERRED_TRANSPORT,
        TripField.HARD_CONSTRAINTS,
    }:
        return (
            _enum_value_set(left)
            == _enum_value_set(right)
        )

    return left == right


def _serialize_value(
    *,
    field: TripField,
    value: Any,
) -> Any:

    if field in {
        TripField.EXCLUDED_TRANSPORT,
        TripField.PREFERRED_TRANSPORT,
        TripField.HARD_CONSTRAINTS,
    }:
        return sorted(
            _enum_value_set(
                value
            )
        )

    if hasattr(
        value,
        "isoformat",
    ):
        return value.isoformat()

    if hasattr(
        value,
        "value",
    ):
        return value.value

    return value


def _enum_value_set(
    value: Any,
) -> set[str]:

    if value is None:
        return set()

    result: set[str] = set()

    for item in value:
        if hasattr(
            item,
            "value",
        ):
            result.add(
                str(item.value)
            )
        else:
            result.add(
                str(item)
            )

    return result