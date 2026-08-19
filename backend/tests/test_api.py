from typing import Any

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from app.agent import get_agent
from app.main import app


class FakeAgent:
    async def ainvoke(self, payload: dict[str, Any]) -> dict[str, list[AIMessage]]:
        message = payload["messages"][0]["content"]
        return {"messages": [AIMessage(content=f"Echo: {message}")]}


app.dependency_overrides[get_agent] = FakeAgent
client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat() -> None:
    response = client.post("/api/v1/agent/chat", json={"message": "Hello"})

    assert response.status_code == 200
    assert response.json() == {"response": "Echo: Hello"}


def test_chat_rejects_empty_message() -> None:
    response = client.post("/api/v1/agent/chat", json={"message": ""})

    assert response.status_code == 422
