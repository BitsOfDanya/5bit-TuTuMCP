from typing import Any, TypedDict

from app.domain.search import SearchOption
from app.domain.travel import AgentTurn, TravelPlan, TripDetails


class TravelWorkflowState(TypedDict, total=False):
    messages: list[Any]
    current_trip: TripDetails
    plan: TravelPlan
    structured_response: AgentTurn
    tools_used: list[str]
    tool_statuses: dict[str, str]
    constraint_result: dict[str, Any]
    search_options: list[SearchOption]
    missing_fields: list[str]
    next_action: str
    redirect_url: str | None
