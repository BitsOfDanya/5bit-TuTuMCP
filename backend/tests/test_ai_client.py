from typing import Any

import httpx
import pytest

from app.ai_client import AIServiceClient
from app.schemas import TripDetails


class FakeAsyncClient:
    request_kwargs: dict[str, Any] = {}

    def __init__(self, **kwargs: Any) -> None:
        FakeAsyncClient.request_kwargs = {"client": kwargs}

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        return None

    async def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        FakeAsyncClient.request_kwargs.update({"method": method, "path": path, "request": kwargs})
        return httpx.Response(
            200,
            request=httpx.Request(method, f"http://ai:8020{path}"),
            json={
                "response": "**Когда хотите поехать?**",
                "trip": {"service_type": "train", "origin": "Москва"},
                "missing_fields": ["destination"],
                "is_complete": False,
                "next_action": "collect_trip_details",
                "plan": {
                    "objective": "Собрать параметры.",
                    "steps": [
                        {"action": "extract_trip_details", "reason": "Извлечь."},
                        {"action": "validate_trip_details", "reason": "Проверить."},
                        {"action": "determine_next_action", "reason": "Выбрать."},
                    ],
                },
                "tools_used": ["validate_trip_details"],
                "tool_statuses": {},
                "redirect_url": None,
            },
        )


@pytest.mark.asyncio
async def test_sends_history_and_parses_ai_service_response(monkeypatch) -> None:
    monkeypatch.setattr("app.ai_client.httpx.AsyncClient", FakeAsyncClient)
    client = AIServiceClient("http://ai:8020", "internal-token", 30)
    result = await client.chat(
        messages=[{"role": "user", "content": "Нужен поезд"}],
        current_trip=TripDetails(),
    )
    assert result.response == "**Когда хотите поехать?**"
    assert result.trip.origin == "Москва"
    assert FakeAsyncClient.request_kwargs["client"]["headers"] == {
        "X-AI-Service-Token": "internal-token"
    }
    assert FakeAsyncClient.request_kwargs["request"]["json"]["messages"] == [
        {"role": "user", "content": "Нужен поезд"}
    ]
