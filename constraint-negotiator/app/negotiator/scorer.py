from app.models.relaxation import ConstraintChange
from app.models.trip import ConstraintField, TripSpec


def score_change(
    trip: TripSpec,
    change: ConstraintChange,
) -> float:

    if change.field == ConstraintField.BUDGET:
        if not trip.budget:
            return 1.0

        return change.magnitude / trip.budget

    if change.field in {
        ConstraintField.OUTBOUND_AFTER,
        ConstraintField.RETURN_BEFORE,
    }:
        return change.magnitude / 120.0

    if change.field == ConstraintField.TRANSPORT:
        return 0.8

    if change.field == ConstraintField.MAX_TRANSFERS:
        return 0.7 * change.magnitude

    return 1.0


def score_plan(
    trip: TripSpec,
    changes: list[ConstraintChange],
) -> float:

    base = sum(
        score_change(trip, change)
        for change in changes
    )

    multi_constraint_penalty = max(
        0,
        len(changes) - 1,
    ) * 0.35

    return base + multi_constraint_penalty