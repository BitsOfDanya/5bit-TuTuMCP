import logging

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import AgentDep
from app.api.schemas import AIChatRequest, AIChatResponse
from app.domain.travel import AgentTurn, TravelPlan

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])


@router.post("/chat")
async def chat(request: AIChatRequest, agent: AgentDep) -> AIChatResponse:
    try:
        result = await agent.ainvoke(
            {
                "messages": [message.model_dump() for message in request.messages],
                "current_trip": request.current_trip,
            }
        )
        turn = AgentTurn.model_validate(result["structured_response"])
        plan = TravelPlan.model_validate(result["plan"])
    except Exception as exc:
        logger.exception("AI workflow invocation failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI workflow could not produce a response.",
        ) from exc
    missing_fields = list(result["missing_fields"])
    return AIChatResponse(
        response=turn.assistant_message,
        trip=turn.trip,
        missing_fields=missing_fields,
        is_complete=not missing_fields,
        next_action=result["next_action"],
        plan=plan,
        tools_used=list(dict.fromkeys(result.get("tools_used", []))),
        tool_statuses=result.get("tool_statuses", {}),
        redirect_url=result.get("redirect_url"),
    )
