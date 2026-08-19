from __future__ import annotations

from collections import defaultdict

from app.models.journey import JourneyOption
from app.models.relaxation import (
    NegotiationResult,
    RelaxationPlan,
)
from app.models.trip import ConstraintField, TripSpec
from app.negotiator.applier import build_relaxed_trip
from app.negotiator.feasibility import evaluate_constraints
from app.negotiator.scorer import score_plan


class ConstraintNegotiator:
    def solve(
        self,
        trip: TripSpec,
        journeys: list[JourneyOption],
        limit: int = 3,
        allow_multi_constraint: bool = False,
    ) -> NegotiationResult:
        """
        Core Constraint Negotiator.

        Default product behaviour:

        1. If feasible journeys exist -> return them.
        2. Otherwise find journeys requiring exactly ONE relaxed constraint.
        3. Return at most one best suggestion per constraint type.
        4. Do NOT silently fill missing slots with multi-constraint proposals.

        Multi-constraint negotiation can later be enabled explicitly.
        """

        feasible: list[JourneyOption] = []

        single_constraint_plans: list[
            RelaxationPlan
        ] = []

        multi_constraint_plans: list[
            RelaxationPlan
        ] = []

        for journey in journeys:
            changes = evaluate_constraints(
                trip=trip,
                journey=journey,
            )

            # -------------------------------------------------
            # Already feasible
            # -------------------------------------------------

            if not changes:
                feasible.append(
                    journey
                )
                continue

            # -------------------------------------------------
            # Never relax HARD constraints
            # -------------------------------------------------

            violates_hard_constraint = any(
                change.field
                in trip.hard_constraints
                for change in changes
            )

            if violates_hard_constraint:
                continue

            relaxed_trip = build_relaxed_trip(
                trip=trip,
                journey=journey,
                changes=changes,
            )

            plan = RelaxationPlan(
                id=(
                    f"relax-"
                    f"{journey.id}"
                ),
                changes=changes,
                score=score_plan(
                    trip=trip,
                    changes=changes,
                ),
                new_trip_spec=relaxed_trip,
                journey=journey,
            )

            if len(changes) == 1:
                single_constraint_plans.append(
                    plan
                )
            else:
                multi_constraint_plans.append(
                    plan
                )

        # -----------------------------------------------------
        # Exact solutions exist
        # -----------------------------------------------------

        if feasible:
            feasible.sort(
                key=lambda item: (
                    item.total_price,
                    item.outbound.departure,
                    item.inbound.arrival,
                )
            )

            return NegotiationResult(
                status="success",
                trip_spec=trip,
                journeys=feasible,
                alternatives=[],
            )

        # -----------------------------------------------------
        # Pick the BEST single relaxation for each field
        # -----------------------------------------------------

        selected = (
            self._select_best_single_plans(
                plans=single_constraint_plans,
                limit=limit,
            )
        )

        # -----------------------------------------------------
        # Multi constraint is NOT used by default.
        #
        # This is intentional:
        #
        # "Change ONE thing and your trip becomes possible."
        # -----------------------------------------------------

        if (
            allow_multi_constraint
            and len(selected) < limit
        ):
            remaining = (
                limit - len(selected)
            )

            selected.extend(
                self._select_best_multi_plans(
                    plans=multi_constraint_plans,
                    limit=remaining,
                )
            )

        if selected:
            return NegotiationResult(
                status="negotiation_required",
                trip_spec=trip,
                journeys=[],
                alternatives=selected,
            )

        return NegotiationResult(
            status="no_options",
            trip_spec=trip,
            journeys=[],
            alternatives=[],
        )

    @staticmethod
    def _select_best_single_plans(
        plans: list[RelaxationPlan],
        limit: int,
    ) -> list[RelaxationPlan]:
        """
        Pick one strongest proposal per constraint type.

        Example:

        budget:
            +7314 ₽
            +9200 ₽
            +15000 ₽

        We only show +7314 ₽.

        Then compare that against best:
            departure relaxation
            return relaxation
            transport relaxation
            etc.
        """

        grouped: dict[
            ConstraintField,
            list[RelaxationPlan],
        ] = defaultdict(list)

        for plan in plans:
            if len(plan.changes) != 1:
                continue

            field = (
                plan.changes[0].field
            )

            grouped[field].append(
                plan
            )

        best_per_field: list[
            RelaxationPlan
        ] = []

        for field_plans in grouped.values():
            field_plans.sort(
                key=lambda plan: (
                    plan.score,
                    plan.journey.total_price,
                    plan.journey.outbound.departure,
                    plan.journey.inbound.arrival,
                )
            )

            best_per_field.append(
                field_plans[0]
            )

        best_per_field.sort(
            key=lambda plan: (
                plan.score,
                plan.journey.total_price,
            )
        )

        return best_per_field[
            :limit
        ]

    @staticmethod
    def _select_best_multi_plans(
        plans: list[RelaxationPlan],
        limit: int,
    ) -> list[RelaxationPlan]:
        """
        Future P1 mode.

        Multi-constraint plans are intentionally separated from
        the primary product flow.
        """

        plans = sorted(
            plans,
            key=lambda plan: (
                len(plan.changes),
                plan.score,
                plan.journey.total_price,
            ),
        )

        return plans[:limit]