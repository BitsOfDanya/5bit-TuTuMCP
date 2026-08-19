from typing import Any

from langchain.tools import BaseTool, tool

from app.agent.tools.travel import (
    ToolTripDetails,
    build_search_redirect,
    determine_next_action,
    validate_trip_details,
)
from app.integrations.constraint_negotiator.client import ConstraintNegotiatorClient


def build_travel_tools(client: ConstraintNegotiatorClient) -> list[BaseTool]:
    @tool
    async def negotiate_constraints(trip: ToolTripDetails) -> dict[str, Any]:
        """Find real journeys or constraint relaxations for a complete round trip."""
        return await client.negotiate(trip.to_domain())

    return [
        validate_trip_details,
        determine_next_action,
        negotiate_constraints,
        build_search_redirect,
    ]
