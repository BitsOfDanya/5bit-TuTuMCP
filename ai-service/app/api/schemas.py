from typing import Literal

from pydantic import BaseModel, Field

from app.domain.documents import PassengerDocumentData
from app.domain.search import SearchOption
from app.domain.travel import AgentNextAction, DecisionIntent, TravelPlan, TripDetails


class AIMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=20_000)


class AIChatRequest(BaseModel):
    messages: list[AIMessage] = Field(min_length=1, max_length=200)
    current_trip: TripDetails = Field(default_factory=TripDetails)


class AIChatResponse(BaseModel):
    response: str
    trip: TripDetails
    missing_fields: list[str]
    is_complete: bool
    next_action: AgentNextAction
    plan: TravelPlan
    tools_used: list[str]
    tool_statuses: dict[str, str]
    search_options: list[SearchOption] = Field(default_factory=list)
    redirect_url: str | None = None
    decision_intent: DecisionIntent = DecisionIntent.SEARCH


class DocumentExtractionResponse(BaseModel):
    media_type: Literal["image/png", "image/jpeg", "application/pdf"]
    document: PassengerDocumentData
    missing_fields: list[str]
    manual_review_required: bool


class ReadinessResponse(BaseModel):
    status: str
    dependencies: dict[str, str]
