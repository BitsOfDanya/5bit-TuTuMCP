from typing import Any, TypedDict

from app.domain.travel import AgentTurn, TravelPlan, TripDetails


class TravelWorkflowState(TypedDict, total=False):
    messages: list[Any]
    current_trip: TripDetails
    plan: TravelPlan
    structured_response: AgentTurn
    tools_used: list[str]
    missing_fields: list[str]
    next_action: str
    redirect_url: str | None
