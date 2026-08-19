from datetime import date, time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.agent.graph import get_agent
from app.domain.documents import IdentityDocumentType, PassengerDocumentData, PassengerSex
from app.domain.travel import (
    AgentTurn,
    PlanAction,
    PlanStep,
    TravelPlan,
    TravelService,
    TripDetails,
)
from app.integrations.constraint_negotiator.client import get_constraint_negotiator_client
from app.integrations.openai.document_extractor import get_document_extractor
from app.main import app


class FakeAgent:
    async def ainvoke(self, _: dict[str, Any]) -> dict[str, Any]:
        trip = TripDetails(
            service_type=TravelService.TRAIN,
            origin="Москва",
            destination="Казань",
            start_date=date(2026, 9, 1),
            preferred_time=time(10, 30),
            passengers=2,
            budget=20_000,
        )
        return {
            "structured_response": AgentTurn(
                assistant_message="**Параметры собраны.**",
                trip=trip,
            ),
            "plan": TravelPlan(
                objective="Подготовить поиск.",
                steps=[
                    PlanStep(action=PlanAction.EXTRACT_TRIP_DETAILS, reason="Извлечь."),
                    PlanStep(action=PlanAction.VALIDATE_TRIP_DETAILS, reason="Проверить."),
                    PlanStep(action=PlanAction.DETERMINE_NEXT_ACTION, reason="Выбрать."),
                ],
            ),
            "missing_fields": [],
            "next_action": "redirect_to_search",
            "tools_used": ["validate_trip_details"],
            "tool_statuses": {},
            "redirect_url": "/search/train?destination=Казань",
        }


class FakeExtractor:
    async def extract(self, **_: Any) -> PassengerDocumentData:
        return PassengerDocumentData(
            document_type=IdentityDocumentType.INTERNATIONAL_PASSPORT,
            first_name="ИВАН",
            last_name="ИВАНОВ",
            first_name_latin="IVAN",
            last_name_latin="IVANOV",
            date_of_birth=date(1990, 1, 2),
            sex=PassengerSex.MALE,
            citizenship="RUS",
            document_number="1234567",
            expiration_date=date(2031, 1, 1),
            issuing_country="RUS",
        )


class FakeConstraintNegotiator:
    async def health(self) -> dict[str, str]:
        return {"status": "ok", "service": "constraint-negotiator"}


@pytest.fixture
def client() -> TestClient:
    app.dependency_overrides[get_agent] = FakeAgent
    app.dependency_overrides[get_document_extractor] = FakeExtractor
    app.dependency_overrides[get_constraint_negotiator_client] = FakeConstraintNegotiator
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_chat_contract(client: TestClient) -> None:
    response = client.post(
        "/api/v1/ai/chat",
        json={"messages": [{"role": "user", "content": "Нужен поезд"}]},
    )
    assert response.status_code == 200
    assert response.json()["response"] == "**Параметры собраны.**"
    assert response.json()["trip"]["service_type"] == "train"


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "jarvell-ai"}


def test_readiness_checks_constraint_negotiator(client: TestClient) -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "dependencies": {"constraint-negotiator": "ok"},
    }


def test_document_contract(client: TestClient) -> None:
    response = client.post(
        "/api/v1/ai/documents/extract",
        files={"document": ("passport.png", b"\x89PNG\r\n\x1a\nimage", "image/png")},
    )
    assert response.status_code == 200
    assert response.json()["document"]["last_name_latin"] == "IVANOV"
    assert response.json()["manual_review_required"] is False
