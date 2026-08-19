import asyncio
from datetime import date, time
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.agent import get_agent
from app.database import initialize_database
from app.document_extraction import get_document_extractor
from app.main import app
from app.schemas import (
    AgentTurn,
    IdentityDocumentType,
    PassengerDocumentData,
    PassengerSex,
    PlanAction,
    PlanStep,
    TravelPlan,
    TravelService,
    TripDetails,
)

USER_ID = uuid4()
OTHER_USER_ID = uuid4()


class FakeAgent:
    async def ainvoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        user_message = next(
            message["content"]
            for message in reversed(payload["messages"])
            if message["role"] == "user"
        )
        if "международ" in user_message.lower():
            turn = AgentTurn(
                assistant_message="Параметры собраны. Загрузите документы пассажира.",
                trip=TripDetails(
                    service_type=TravelService.FLIGHT,
                    origin="Москва",
                    destination="Париж",
                    start_date=date(2026, 9, 1),
                    preferred_time=time(10, 30),
                    passengers=1,
                    budget=50_000,
                    is_international=True,
                ),
            )
        elif "Моск" in user_message:
            turn = AgentTurn(
                assistant_message="Понял маршрут. Когда хотите поехать?",
                trip=TripDetails(
                    service_type=TravelService.TRAIN,
                    origin="Москва",
                    destination="Казань",
                ),
            )
        else:
            turn = AgentTurn(
                assistant_message="Все параметры собраны.",
                trip=TripDetails(
                    start_date=date(2026, 9, 1),
                    preferred_time=time(10, 30),
                    passengers=2,
                    budget=20_000,
                ),
            )

        return {
            "structured_response": turn,
            "plan": TravelPlan(
                objective="Обновить поездку и определить следующий шаг.",
                steps=[
                    PlanStep(
                        action=PlanAction.EXTRACT_TRIP_DETAILS,
                        reason="Извлечь данные.",
                    ),
                    PlanStep(
                        action=PlanAction.VALIDATE_TRIP_DETAILS,
                        reason="Проверить поля.",
                    ),
                    PlanStep(
                        action=PlanAction.DETERMINE_NEXT_ACTION,
                        reason="Выбрать следующий этап.",
                    ),
                ],
            ),
            "tools_used": ["validate_trip_details", "determine_next_action"],
        }


class FakeDocumentExtractor:
    async def extract(self, **_: Any) -> PassengerDocumentData:
        return PassengerDocumentData(
            document_type=IdentityDocumentType.INTERNATIONAL_PASSPORT,
            last_name="ИВАНОВ",
            first_name="ИВАН",
            last_name_latin="IVANOV",
            first_name_latin="IVAN",
            date_of_birth=date(1990, 1, 2),
            sex=PassengerSex.MALE,
            citizenship="RUS",
            document_series="72",
            document_number="1234567",
            expiration_date=date(2031, 5, 10),
            issuing_country="RUS",
        )


@pytest.fixture
def client() -> TestClient:
    asyncio.run(initialize_database())
    app.dependency_overrides[get_agent] = FakeAgent
    app.dependency_overrides[get_document_extractor] = FakeDocumentExtractor
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_returns_plan_and_persists_history(client: TestClient) -> None:
    first = client.post(
        "/api/v1/agent/chat",
        json={"user_id": str(USER_ID), "message": "Нужен поезд из Москвы в Казань"},
    )

    assert first.status_code == 200
    first_body = first.json()
    assert first_body["trip"]["service_type"] == "train"
    assert first_body["next_action"] == "collect_trip_details"
    assert first_body["tools_used"] == ["validate_trip_details", "determine_next_action"]
    assert [step["action"] for step in first_body["plan"]["steps"]] == [
        "extract_trip_details",
        "validate_trip_details",
        "determine_next_action",
    ]

    session_id = first_body["session_id"]
    second = client.post(
        "/api/v1/agent/chat",
        json={
            "user_id": str(USER_ID),
            "session_id": session_id,
            "message": "1 сентября в 10:30, двое пассажиров, бюджет 20 тысяч",
        },
    )

    assert second.status_code == 200
    second_body = second.json()
    assert second_body["is_complete"] is True
    assert second_body["next_action"] == "redirect_to_search"
    assert second_body["redirect_url"].startswith("/search/train?")

    history = client.get(
        f"/api/v1/agent/users/{USER_ID}/sessions/{session_id}"
    ).json()
    assert [message["role"] for message in history["messages"]] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]
    assert history["redirect_url"] == second_body["redirect_url"]


def test_conversation_is_isolated_by_user(client: TestClient) -> None:
    session_id = client.post(
        "/api/v1/agent/chat",
        json={"user_id": str(USER_ID), "message": "Нужен поезд из Москвы в Казань"},
    ).json()["session_id"]

    response = client.get(f"/api/v1/agent/users/{OTHER_USER_ID}/sessions/{session_id}")
    assert response.status_code == 404


def test_international_flight_routes_to_document_extraction(client: TestClient) -> None:
    chat = client.post(
        "/api/v1/agent/chat",
        json={
            "user_id": str(USER_ID),
            "message": "Нужен международный рейс из Москвы в Париж",
        },
    )
    assert chat.status_code == 200
    assert chat.json()["next_action"] == "upload_passenger_documents"
    session_id = chat.json()["session_id"]

    extraction = client.post(
        f"/api/v1/agent/users/{USER_ID}/sessions/{session_id}/documents/extract",
        files={"document": ("passport.png", b"\x89PNG\r\n\x1a\nimage", "image/png")},
    )

    assert extraction.status_code == 200
    body = extraction.json()
    assert body["document"]["document_type"] == "international_passport"
    assert body["document"]["last_name_latin"] == "IVANOV"
    assert body["manual_review_required"] is False


def test_chat_rejects_empty_message(client: TestClient) -> None:
    response = client.post(
        "/api/v1/agent/chat",
        json={"user_id": str(USER_ID), "message": ""},
    )
    assert response.status_code == 422
