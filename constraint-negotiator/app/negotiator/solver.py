from app.models.journey import JourneyOption
from app.models.relaxation import (
    NegotiationResult,
    RelaxationPlan,
)
from app.models.trip import TripSpec
from app.negotiator.feasibility import evaluate_constraints
from app.negotiator.scorer import score_plan


class ConstraintNegotiator:
    def solve(
        self,
        trip: TripSpec,
        journeys: list[JourneyOption],
        limit: int = 3,
    ) -> NegotiationResult:

        feasible: list[JourneyOption] = []
        plans: list[RelaxationPlan] = []

        for journey in journeys:
            changes = evaluate_constraints(
                trip=trip,
                journey=journey,
            )

            if not changes:
                feasible.append(journey)
                continue

            violates_hard_constraint = any(
                change.field in trip.hard_constraints
                for change in changes
            )

            if violates_hard_constraint:
                continue

            plan = RelaxationPlan(
                id=f"relax-{journey.id}",
                changes=changes,
                score=score_plan(
                    trip=trip,
                    changes=changes,
                ),
                journey=journey,
            )

            plans.append(plan)

        if feasible:
            feasible.sort(
                key=lambda item: item.total_price
            )

            return NegotiationResult(
                status="success",
                trip_spec=trip,
                journeys=feasible,
                alternatives=[],
            )

        if not plans:
            return NegotiationResult(
                status="no_options",
                trip_spec=trip,
                journeys=[],
                alternatives=[],
            )

        plans.sort(
            key=lambda item: (
                len(item.changes),
                item.score,
                item.journey.total_price,
            )
        )

        selected = self._select_diverse_plans(
            plans=plans,
            limit=limit,
        )

        return NegotiationResult(
            status="negotiation_required",
            trip_spec=trip,
            journeys=[],
            alternatives=selected,
        )

    @staticmethod
    def _select_diverse_plans(
        plans: list[RelaxationPlan],
        limit: int,
    ) -> list[RelaxationPlan]:

        selected: list[RelaxationPlan] = []
        used_primary_fields: set[str] = set()

        for plan in plans:
            if not plan.changes:
                continue

            primary = plan.changes[0].field.value

            if primary in used_primary_fields:
                continue

            selected.append(plan)
            used_primary_fields.add(primary)

            if len(selected) >= limit:
                return selected

        for plan in plans:
            if plan in selected:
                continue

            selected.append(plan)

            if len(selected) >= limit:
                break

        return selected