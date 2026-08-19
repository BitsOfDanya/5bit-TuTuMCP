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
from app.negotiator.scorer import (
    score_change,
    score_plan,
)


class ConstraintNegotiator:
    def solve(
        self,
        trip: TripSpec,
        journeys: list[JourneyOption],
        limit: int = 3,
        allow_combination_fallback: bool = True,
    ) -> NegotiationResult:
        """
        Constraint negotiation strategy.

        Priority:

        1. Exact feasible journeys.
        2. Best single-constraint relaxations.
        3. Pareto-efficient two-constraint combinations.
        4. Never expose 3+ constraint compromises
           in the primary negotiation flow.

        Hard constraints are never relaxed.
        """

        feasible: list[JourneyOption] = []

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
            # Exact feasible journey
            # -------------------------------------------------

            if not changes:
                feasible.append(
                    journey
                )
                continue

            # -------------------------------------------------
            # Hard constraints cannot be negotiated
            # -------------------------------------------------

            violates_hard_constraint = any(
                change.field
                in trip.hard_constraints
                for change in changes
            )

            if violates_hard_constraint:
                continue

            # -------------------------------------------------
            # Primary UI stops at two changes
            # -------------------------------------------------

            if len(changes) > 2:
                continue

            relaxed_trip = build_relaxed_trip(
                trip=trip,
                journey=journey,
                changes=changes,
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
                new_trip_spec=relaxed_trip,
                journey=journey,
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
        # Exact solutions always win
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
        # Best single relaxation for each field
        # -----------------------------------------------------

        selected = (
            self._select_best_single_plans(
                plans=single_plans,
                limit=limit,
            )
        )

        # -----------------------------------------------------
        # Pareto combinations only as fallback
        # -----------------------------------------------------

        if (
            allow_combination_fallback
            and len(selected) < limit
        ):
            remaining = (
                limit - len(selected)
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
        """
        Keep only the best concrete journey
        for every individual constraint field.
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

        return best_per_field[:limit]

    @classmethod
    def _select_pareto_combinations(
        cls,
        *,
        trip: TripSpec,
        plans: list[RelaxationPlan],
        limit: int,
        already_selected: list[RelaxationPlan],
    ) -> list[RelaxationPlan]:
        """
        Select meaningful two-constraint compromises.

        A combination is removed when:

        - another combination dominates it;
        - OR an already selected single relaxation
          dominates it.

        This prevents nonsense such as:

            +13 864 ₽

        being shown together with:

            +16 892 ₽
            +25 minutes

        because the first proposal is strictly better.
        """

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

        # -----------------------------------------------------
        # First remove combinations dominated by
        # another combination.
        # -----------------------------------------------------

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

        # -----------------------------------------------------
        # Then remove combinations dominated by an
        # already selected SINGLE plan.
        #
        # This was the missing piece.
        # -----------------------------------------------------

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

        # -----------------------------------------------------
        # Avoid duplicate concrete journey
        # -----------------------------------------------------

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

        return final_frontier[:limit]

    @staticmethod
    def _deduplicate_combinations(
        plans: list[RelaxationPlan],
    ) -> list[RelaxationPlan]:
        """
        For each identical pair of relaxed fields
        keep the best concrete journey.

        Example:

            budget + transport
            budget + transport
            budget + transport

        -> one best candidate.
        """

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
                best[signature] = plan
                continue

            candidate_key = (
                plan.score,
                plan.journey.total_price,
            )

            current_key = (
                current.score,
                current.journey.total_price,
            )

            if candidate_key < current_key:
                best[signature] = plan

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
        """
        Convert a relaxation into comparable
        normalized inconvenience dimensions.

        An untouched constraint has cost 0.
        """

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
        """
        Pareto dominance:

        left dominates right when it is
        no worse on every constraint dimension
        and strictly better on at least one.
        """

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