from __future__ import annotations

from dataclasses import dataclass

from app.models.relaxation import ConstraintChange
from app.models.trip import (
    ConstraintField,
    TripSpec,
)


@dataclass(
    frozen=True,
    slots=True,
)
class NegotiationPolicy:
    """
    Product-level bounds for reasonable negotiations.

    Solver may mathematically find many feasible
    relaxations, but not every relaxation is useful
    enough to show to a person.

    These limits define what may appear in the
    primary negotiation UI.
    """

    max_outbound_shift_minutes: int = 180
    max_return_shift_minutes: int = 180

    max_extra_transfers: int = 1

    # Example:
    # original budget = 20 000
    # max_budget_increase_ratio = 1.0
    #
    # maximum suggested budget increase = +20 000.
    max_budget_increase_ratio: float = 1.0

    def is_change_reasonable(
        self,
        *,
        trip: TripSpec,
        change: ConstraintChange,
    ) -> bool:
        field = change.field

        # -----------------------------------------------------
        # Budget
        # -----------------------------------------------------

        if field == ConstraintField.BUDGET:
            if trip.budget is None:
                return True

            max_increase = (
                trip.budget
                * self.max_budget_increase_ratio
            )

            return (
                change.magnitude
                <= max_increase
            )

        # -----------------------------------------------------
        # Departure time
        # -----------------------------------------------------

        if (
            field
            == ConstraintField.OUTBOUND_AFTER
        ):
            return (
                change.magnitude
                <= self.max_outbound_shift_minutes
            )

        # -----------------------------------------------------
        # Return time
        # -----------------------------------------------------

        if (
            field
            == ConstraintField.RETURN_BEFORE
        ):
            return (
                change.magnitude
                <= self.max_return_shift_minutes
            )

        # -----------------------------------------------------
        # Transfers
        # -----------------------------------------------------

        if (
            field
            == ConstraintField.MAX_TRANSFERS
        ):
            return (
                change.magnitude
                <= self.max_extra_transfers
            )

        # -----------------------------------------------------
        # Transport
        # -----------------------------------------------------

        if (
            field
            == ConstraintField.TRANSPORT
        ):
            return True

        return True

    def is_plan_reasonable(
        self,
        *,
        trip: TripSpec,
        changes: list[ConstraintChange],
    ) -> bool:
        return all(
            self.is_change_reasonable(
                trip=trip,
                change=change,
            )
            for change in changes
        )