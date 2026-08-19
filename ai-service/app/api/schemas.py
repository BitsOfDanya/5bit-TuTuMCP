from typing import Literal

from pydantic import BaseModel, Field

from app.domain.documents import PassengerDocumentData
from app.domain.travel import AgentNextAction, TravelPlan, TripDetails


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
    redirect_url: str | None = None


class DocumentExtractionResponse(BaseModel):
    media_type: Literal["image/png", "image/jpeg", "application/pdf"]
    document: PassengerDocumentData
    missing_fields: list[str]
    manual_review_required: bool
