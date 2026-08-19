from __future__ import annotations

from collections import defaultdict

from app.models.journey import JourneyOption
from app.models.relaxation import (
    NegotiationResult,
    RelaxationPlan,
)
from app.models.trip import (
    ConstraintField,
    TripSpec,
)
from app.negotiator.applier import (
    build_relaxed_trip,
)
from app.negotiator.feasibility import (
    evaluate_constraints,
)
from app.negotiator.policy import (
    NegotiationPolicy,
)
from app.negotiator.presenter import (
    build_relaxation_summary,
)
from app.negotiator.scorer import (
    score_change,
    score_plan,
)


class ConstraintNegotiator:
    def __init__(
        self,
        policy: NegotiationPolicy | None = None,
    ) -> None:
        self.policy = (
            policy
            or NegotiationPolicy()
        )

    def solve(
        self,
        trip: TripSpec,
        journeys: list[JourneyOption],
        limit: int = 3,
        allow_combination_fallback: bool = True,
    ) -> NegotiationResult:

        feasible: list[
            JourneyOption
        ] = []

        single_plans: list[
            RelaxationPlan
        ] = []

        combination_plans: list[
            RelaxationPlan
        ] = []

        for journey in journeys:
            changes = evaluate_constraints(
                trip=trip,
                journey=journey,
            )

            # -------------------------------------------------
            # Exact solution
            # -------------------------------------------------

            if not changes:
                feasible.append(
                    journey
                )
                continue

            # -------------------------------------------------
            # Hard constraints
            # -------------------------------------------------

            violates_hard = any(
                change.field
                in trip.hard_constraints
                for change in changes
            )

            if violates_hard:
                continue

            # -------------------------------------------------
            # Do not show complex 3+ change negotiations
            # -------------------------------------------------

            if len(changes) > 2:
                continue

            # -------------------------------------------------
            # Product policy
            #
            # Mathematically possible does not necessarily
            # mean useful for a human.
            # -------------------------------------------------

            if not (
                self.policy
                .is_plan_reasonable(
                    trip=trip,
                    changes=changes,
                )
            ):
                continue

            relaxed_trip = (
                build_relaxed_trip(
                    trip=trip,
                    journey=journey,
                    changes=changes,
                )
            )

            kind = (
                "single"
                if len(changes) == 1
                else "combination"
            )

            plan = RelaxationPlan(
                id=(
                    f"relax-"
                    f"{journey.id}"
                ),
                kind=kind,
                changes=changes,
                score=score_plan(
                    trip=trip,
                    changes=changes,
                ),
                new_trip_spec=(
                    relaxed_trip
                ),
                journey=journey,
                summary=(
                    build_relaxation_summary(
                        journey=journey,
                        changes=changes,
                    )
                ),
            )

            if len(changes) == 1:
                single_plans.append(
                    plan
                )
            else:
                combination_plans.append(
                    plan
                )

        # -----------------------------------------------------
        # Exact journeys always win
        # -----------------------------------------------------

        if feasible:
            feasible.sort(
                key=lambda journey: (
                    journey.total_price,
                    journey.outbound.departure,
                    journey.inbound.arrival,
                )
            )

            return NegotiationResult(
                status="success",
                trip_spec=trip,
                journeys=feasible,
                alternatives=[],
            )

        # -----------------------------------------------------
        # Best single relaxation per constraint
        # -----------------------------------------------------

        selected = (
            self._select_best_single_plans(
                plans=single_plans,
                limit=limit,
            )
        )

        # -----------------------------------------------------
        # Pareto combinations
        # -----------------------------------------------------

        if (
            allow_combination_fallback
            and len(selected) < limit
        ):
            remaining = (
                limit
                - len(selected)
            )

            combinations = (
                self._select_pareto_combinations(
                    trip=trip,
                    plans=combination_plans,
                    limit=remaining,
                    already_selected=selected,
                )
            )

            selected.extend(
                combinations
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

    @classmethod
    def _select_pareto_combinations(
        cls,
        *,
        trip: TripSpec,
        plans: list[RelaxationPlan],
        limit: int,
        already_selected: list[RelaxationPlan],
    ) -> list[RelaxationPlan]:

        candidates = [
            plan
            for plan in plans
            if len(plan.changes) == 2
        ]

        if not candidates:
            return []

        candidates = (
            cls._deduplicate_combinations(
                candidates
            )
        )

        combination_frontier = [
            candidate
            for candidate in candidates
            if not any(
                cls._dominates(
                    trip=trip,
                    left=other,
                    right=candidate,
                )
                for other in candidates
                if (
                    other.id
                    != candidate.id
                )
            )
        ]

        final_frontier = [
            candidate
            for candidate
            in combination_frontier
            if not any(
                cls._dominates(
                    trip=trip,
                    left=selected,
                    right=candidate,
                )
                for selected
                in already_selected
            )
        ]

        selected_journey_ids = {
            plan.journey.id
            for plan
            in already_selected
        }

        final_frontier = [
            plan
            for plan
            in final_frontier
            if (
                plan.journey.id
                not in selected_journey_ids
            )
        ]

        final_frontier.sort(
            key=lambda plan: (
                plan.score,
                plan.journey.total_price,
                cls._field_signature(
                    plan
                ),
            )
        )

        return final_frontier[
            :limit
        ]

    @staticmethod
    def _deduplicate_combinations(
        plans: list[RelaxationPlan],
    ) -> list[RelaxationPlan]:

        best: dict[
            tuple[str, ...],
            RelaxationPlan,
        ] = {}

        for plan in plans:
            signature = (
                ConstraintNegotiator
                ._field_signature(
                    plan
                )
            )

            current = best.get(
                signature
            )

            if current is None:
                best[
                    signature
                ] = plan

                continue

            candidate_key = (
                plan.score,
                plan.journey.total_price,
            )

            current_key = (
                current.score,
                current.journey.total_price,
            )

            if (
                candidate_key
                < current_key
            ):
                best[
                    signature
                ] = plan

        return list(
            best.values()
        )

    @staticmethod
    def _field_signature(
        plan: RelaxationPlan,
    ) -> tuple[str, ...]:

        return tuple(
            sorted(
                change.field.value
                for change
                in plan.changes
            )
        )

    @staticmethod
    def _change_vector(
        *,
        trip: TripSpec,
        plan: RelaxationPlan,
    ) -> dict[
        ConstraintField,
        float,
    ]:

        vector = {
            field: 0.0
            for field
            in ConstraintField
        }

        for change in plan.changes:
            vector[
                change.field
            ] = score_change(
                trip=trip,
                change=change,
            )

        return vector

    @classmethod
    def _dominates(
        cls,
        *,
        trip: TripSpec,
        left: RelaxationPlan,
        right: RelaxationPlan,
    ) -> bool:

        left_vector = (
            cls._change_vector(
                trip=trip,
                plan=left,
            )
        )

        right_vector = (
            cls._change_vector(
                trip=trip,
                plan=right,
            )
        )

        no_worse = all(
            left_vector[field]
            <= right_vector[field]
            for field
            in ConstraintField
        )

        strictly_better = any(
            left_vector[field]
            < right_vector[field]
            for field
            in ConstraintField
        )

        return (
            no_worse
            and strictly_better
        )