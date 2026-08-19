import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.agent import get_agent, message_text
from app.schemas import AgentRequest, AgentResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])
AgentDep = Annotated[Any, Depends(get_agent)]


@router.post("/chat")
async def chat_with_agent(request: AgentRequest, agent: AgentDep) -> AgentResponse:
    try:
        result = await agent.ainvoke({"messages": [{"role": "user", "content": request.message}]})
        response = message_text(result["messages"][-1])
    except Exception as exc:
        logger.exception("Agent invocation failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The agent could not produce a response.",
        ) from exc

    return AgentResponse(response=response)
