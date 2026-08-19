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
                "search_options": [
                    {
                        "id": "journey-1",
                        "kind": "journey",
                        "title": "Москва — Казань",
                        "total_price": 18_900,
                        "currency": "RUB",
                        "outbound": {
                            "mode": "train",
                            "origin": "Москва",
                            "destination": "Казань",
                            "departure": "2026-09-01T10:00:00+03:00",
                            "arrival": "2026-09-01T21:30:00+03:00",
                            "price": 9_500,
                        },
                        "inbound": {
                            "mode": "train",
                            "origin": "Казань",
                            "destination": "Москва",
                            "departure": "2026-09-05T18:00:00+03:00",
                            "arrival": "2026-09-06T05:30:00+03:00",
                            "price": 9_400,
                        },
                        "action_url": "https://www.tutu.ru/poezda/view_d.php?np=002E",
                    }
                ],
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
    assert result.search_options[0].total_price == 18_900
    assert result.search_options[0].action_url.startswith("https://www.tutu.ru/")
    assert FakeAsyncClient.request_kwargs["client"]["headers"] == {
        "X-AI-Service-Token": "internal-token"
    }
    assert FakeAsyncClient.request_kwargs["request"]["json"]["messages"] == [
        {"role": "user", "content": "Нужен поезд"}
    ]
