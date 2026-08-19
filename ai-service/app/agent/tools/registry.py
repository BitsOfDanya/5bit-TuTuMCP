from typing import Any

from langchain.tools import BaseTool, tool

from app.agent.tools.price_analysis import PurchaseTimingAnalyzer
from app.agent.tools.travel import (
    ToolTripDetails,
    build_search_redirect,
    determine_next_action,
    validate_trip_details,
)
from app.integrations.constraint_negotiator.client import ConstraintNegotiatorClient
from app.integrations.smart_trip_tracker.client import SmartTripTrackerClient


def build_travel_tools(
    client: ConstraintNegotiatorClient,
    tracker: SmartTripTrackerClient,
) -> list[BaseTool]:
    price_analyzer = PurchaseTimingAnalyzer(client, tracker)

    @tool
    async def negotiate_constraints(trip: ToolTripDetails) -> dict[str, Any]:
        """Find real Tutu options for train, flight, bus, or hotel searches."""
        return await client.negotiate(trip.to_domain())

    @tool
    async def analyze_purchase_timing(trip: ToolTripDetails) -> dict[str, Any]:
        """Use Smart Trip Tracker price history to decide whether to buy a ticket now."""
        return await price_analyzer.analyze(trip.to_domain())

    return [
        validate_trip_details,
        determine_next_action,
        negotiate_constraints,
        analyze_purchase_timing,
        build_search_redirect,
    ]
