from __future__ import annotations

from app.models.journey import JourneyOption
from app.models.relaxation import ConstraintChange
from app.models.trip import ConstraintField, TripSpec


def build_relaxed_trip(
    trip: TripSpec,
    journey: JourneyOption,
    changes: list[ConstraintChange],
) -> TripSpec:
    """
    Build the exact TripSpec that makes the proposed journey feasible.

    We derive values from the REAL journey instead of trying to reconstruct
    them later on the frontend.
    """

    updates: dict = {}

    changed_fields = {
        change.field
        for change in changes
    }

    # ---------------------------------------------------------
    # Budget
    # ---------------------------------------------------------

    if ConstraintField.BUDGET in changed_fields:
        updates["budget"] = journey.total_price

    # ---------------------------------------------------------
    # Outbound departure
    # ---------------------------------------------------------

    if ConstraintField.OUTBOUND_AFTER in changed_fields:
        actual_departure = (
            journey.outbound.departure
            .replace(tzinfo=None)
        )

        updates["outbound_date"] = (
            actual_departure.date()
        )

        updates["outbound_after"] = (
            actual_departure.time()
        )

    # ---------------------------------------------------------
    # Return arrival
    # ---------------------------------------------------------

    if ConstraintField.RETURN_BEFORE in changed_fields:
        actual_return = (
            journey.inbound.arrival
            .replace(tzinfo=None)
        )

        updates["return_date"] = (
            actual_return.date()
        )

        updates["return_before"] = (
            actual_return.time()
        )

    # ---------------------------------------------------------
    # Transport exclusion
    # ---------------------------------------------------------

    if ConstraintField.TRANSPORT in changed_fields:
        used_modes = (
            journey.transport_modes
        )

        updates["excluded_transport"] = [
            mode
            for mode
            in trip.excluded_transport
            if mode not in used_modes
        ]

    # ---------------------------------------------------------
    # Transfers
    # ---------------------------------------------------------

    if ConstraintField.MAX_TRANSFERS in changed_fields:
        updates["max_transfers"] = (
            journey.max_transfers
        )

    return trip.model_copy(
        update=updates,
        deep=True,
    )