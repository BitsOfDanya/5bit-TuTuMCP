from __future__ import annotations

from datetime import date

from langgraph.graph import (
    END,
    START,
    StateGraph,
)

from app.ai.parser import (
    TripParser,
    get_trip_parser,
)
from app.graph.state import NegotiatorState
from app.models.journey import JourneyOption
from app.models.trip import TripSpec
from app.negotiator.solver import (
    ConstraintNegotiator,
)
from app.search.base import JourneyProvider
from app.tutu.provider import (
    TutuMCPJourneyProvider,
)


def build_negotiator_graph(
    provider: JourneyProvider,
    solver: ConstraintNegotiator,
    parser: TripParser | None = None,
):
    async def resolve_trip(
        state: NegotiatorState,
    ) -> dict:
        existing = state.get(
            "trip_spec"
        )

        # ---------------------------------------------
        # Structured request:
        # LLM is not needed at all.
        # ---------------------------------------------

        if existing is not None:
            trip = TripSpec.model_validate(
                existing
            )

            return {
                "trip_spec": (
                    trip.model_dump(
                        mode="json"
                    )
                )
            }

        # ---------------------------------------------
        # Natural-language request
        # ---------------------------------------------

        request_text = state.get(
            "request_text"
        )

        if not request_text:
            raise ValueError(
                "request_text or trip_spec "
                "is required"
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
            if parser is not None
            else get_trip_parser()
        )

        trip = await active_parser.parse(
            message=request_text,
            reference_date=reference_date,
        )

        return {
            "trip_spec": (
                trip.model_dump(
                    mode="json"
                )
            )
        }

    async def search_candidates(
        state: NegotiatorState,
    ) -> dict:
        trip = TripSpec.model_validate(
            state["trip_spec"]
        )

        journeys = (
            await provider.search_candidates(
                trip
            )
        )

        return {
            "candidate_journeys": [
                journey.model_dump(
                    mode="json"
                )
                for journey in journeys
            ]
        }

    def negotiate(
        state: NegotiatorState,
    ) -> dict:
        trip = TripSpec.model_validate(
            state["trip_spec"]
        )

        journeys = [
            JourneyOption.model_validate(
                item
            )
            for item in state[
                "candidate_journeys"
            ]
        ]

        result = solver.solve(
            trip=trip,
            journeys=journeys,
        )

        return {
            "result": (
                result.model_dump(
                    mode="json"
                )
            )
        }

    builder = StateGraph(
        NegotiatorState
    )

    builder.add_node(
        "resolve_trip",
        resolve_trip,
    )

    builder.add_node(
        "search_candidates",
        search_candidates,
    )

    builder.add_node(
        "negotiate",
        negotiate,
    )

    builder.add_edge(
        START,
        "resolve_trip",
    )

    builder.add_edge(
        "resolve_trip",
        "search_candidates",
    )

    builder.add_edge(
        "search_candidates",
        "negotiate",
    )

    builder.add_edge(
        "negotiate",
        END,
    )

    return builder.compile()


journey_provider = (
    TutuMCPJourneyProvider()
)

constraint_negotiator = (
    ConstraintNegotiator()
)

negotiator_graph = (
    build_negotiator_graph(
        provider=journey_provider,
        solver=constraint_negotiator,
    )
)