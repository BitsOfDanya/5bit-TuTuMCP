from __future__ import annotations

from datetime import date

from langgraph.graph import (
    END,
    START,
    StateGraph,
)

from app.ai.parser import (
    get_trip_update_parser,
)
from app.graph.state import (
    RescueState,
)
from app.models.journey import (
    JourneyOption,
)
from app.models.rescue import (
    RescueExecutionResult,
    RescuePlanningResult,
    RescueValidation,
    TripDiff,
)
from app.models.trip import (
    TripSpec,
)
from app.rescue.diff import (
    build_trip_diff,
)
from app.rescue.planner import (
    build_rescue_search_plans,
)
from app.rescue.validator import (
    validate_current_journey,
)
from app.tutu.rescue_provider import (
    RescueTutuProvider,
)


def build_rescue_graph(
    *,
    provider: RescueTutuProvider | None = None,
    parser=None,
):
    active_provider = (
        provider
        or RescueTutuProvider()
    )

    async def resolve_updated_trip(
        state: RescueState,
    ) -> dict:
        existing = state.get(
            "updated_trip"
        )

        if existing is not None:
            updated = (
                TripSpec.model_validate(
                    existing
                )
            )

            return {
                "updated_trip": (
                    updated.model_dump(
                        mode="json"
                    )
                )
            }

        request_text = state.get(
            "request_text"
        )

        if not request_text:
            raise ValueError(
                "request_text or updated_trip is required"
            )

        previous = (
            TripSpec.model_validate(
                state["previous_trip"]
            )
        )

        reference_date_raw = (
            state.get(
                "reference_date"
            )
        )

        reference_date = (
            date.fromisoformat(
                reference_date_raw
            )
            if reference_date_raw
            else date.today()
        )

        active_parser = (
            parser
            or get_trip_update_parser()
        )

        updated = (
            await active_parser.parse(
                previous_trip=previous,
                message=request_text,
                reference_date=reference_date,
            )
        )

        return {
            "updated_trip": (
                updated.model_dump(
                    mode="json"
                )
            )
        }

    def diff_trip(
        state: RescueState,
    ) -> dict:
        previous = (
            TripSpec.model_validate(
                state["previous_trip"]
            )
        )

        updated = (
            TripSpec.model_validate(
                state["updated_trip"]
            )
        )

        diff = build_trip_diff(
            previous=previous,
            updated=updated,
        )

        return {
            "diff": diff.model_dump(
                mode="json"
            )
        }

    def validate_journey(
        state: RescueState,
    ) -> dict:
        updated = (
            TripSpec.model_validate(
                state["updated_trip"]
            )
        )

        journey = (
            JourneyOption.model_validate(
                state["current_journey"]
            )
        )

        diff = (
            TripDiff.model_validate(
                state["diff"]
            )
        )

        validation = (
            validate_current_journey(
                trip=updated,
                journey=journey,
                diff=diff,
            )
        )

        return {
            "validation": (
                validation.model_dump(
                    mode="json"
                )
            )
        }

    def plan_rescue(
        state: RescueState,
    ) -> dict:
        updated = (
            TripSpec.model_validate(
                state["updated_trip"]
            )
        )

        journey = (
            JourneyOption.model_validate(
                state["current_journey"]
            )
        )

        validation = (
            RescueValidation
            .model_validate(
                state["validation"]
            )
        )

        planning = (
            build_rescue_search_plans(
                trip=updated,
                journey=journey,
                validation=validation,
            )
        )

        return {
            "planning": (
                planning.model_dump(
                    mode="json"
                )
            )
        }

    def route_after_plan(
        state: RescueState,
    ) -> str:
        planning = (
            RescuePlanningResult
            .model_validate(
                state["planning"]
            )
        )

        if (
            planning.status
            == "no_change"
        ):
            return "finalize"

        return "execute"

    async def execute_rescue(
        state: RescueState,
    ) -> dict:
        updated = (
            TripSpec.model_validate(
                state["updated_trip"]
            )
        )

        journey = (
            JourneyOption.model_validate(
                state["current_journey"]
            )
        )

        planning = (
            RescuePlanningResult
            .model_validate(
                state["planning"]
            )
        )

        execution = (
            await active_provider
            .search_replans(
                trip=updated,
                current_journey=journey,
                planning=planning,
            )
        )

        return {
            "execution": (
                execution.model_dump(
                    mode="json"
                )
            )
        }

    def finalize(
        state: RescueState,
    ) -> dict:
        planning = (
            RescuePlanningResult
            .model_validate(
                state["planning"]
            )
        )

        execution_raw = (
            state.get(
                "execution"
            )
        )

        if execution_raw is None:
            execution = (
                RescueExecutionResult(
                    status="no_change",
                    candidates=[],
                )
            )
        else:
            execution = (
                RescueExecutionResult
                .model_validate(
                    execution_raw
                )
            )

        result = {
            "status": (
                execution.status
            ),
            "previous_trip": (
                state["previous_trip"]
            ),
            "updated_trip": (
                state["updated_trip"]
            ),
            "diff": state["diff"],
            "validation": (
                state["validation"]
            ),
            "planning": (
                planning.model_dump(
                    mode="json"
                )
            ),
            "execution": (
                execution.model_dump(
                    mode="json"
                )
            ),
        }

        return {
            "result": result
        }

    graph = StateGraph(
        RescueState
    )

    graph.add_node(
        "resolve_updated_trip",
        resolve_updated_trip,
    )

    graph.add_node(
        "diff",
        diff_trip,
    )

    graph.add_node(
        "validate",
        validate_journey,
    )

    graph.add_node(
        "plan",
        plan_rescue,
    )

    graph.add_node(
        "execute",
        execute_rescue,
    )

    graph.add_node(
        "finalize",
        finalize,
    )

    graph.add_edge(
        START,
        "resolve_updated_trip",
    )

    graph.add_edge(
        "resolve_updated_trip",
        "diff",
    )

    graph.add_edge(
        "diff",
        "validate",
    )

    graph.add_edge(
        "validate",
        "plan",
    )

    graph.add_conditional_edges(
        "plan",
        route_after_plan,
        {
            "execute": "execute",
            "finalize": "finalize",
        },
    )

    graph.add_edge(
        "execute",
        "finalize",
    )

    graph.add_edge(
        "finalize",
        END,
    )

    return graph.compile()


rescue_graph = (
    build_rescue_graph()
)