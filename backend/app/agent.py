from functools import lru_cache
from typing import Any

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from app.config import get_settings


@lru_cache
def get_agent() -> Any:
    """Build the process-wide, stateless LangChain agent."""
    settings = get_settings()
    model = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key.get_secret_value(),
    )
    return create_agent(
        model=model,
        tools=[],
        system_prompt=settings.agent_system_prompt,
    )


def message_text(message: Any) -> str:
    """Normalize LangChain text content into the API's string response."""
    content = message.content
    if isinstance(content, str):
        return content

    text_parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            text_parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            text_parts.append(str(block.get("text", "")))

    return "".join(text_parts)
