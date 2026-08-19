from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.db import get_session
from app.main import app
from app.trip_rescue_client import get_trip_rescue_client


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def override_session() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_session, None)


class FakeTripRescueClient:
    def __init__(self) -> None:
        self.completed_with: dict[str, object] | None = None

    async def get_cold_start_questions(self, *, limit: int = 4) -> dict[str, object]:
        return {
            "total": limit,
            "minimum_choices": 4,
            "questions": [_question(index) for index in range(limit)],
        }

    async def complete_cold_start(
        self,
        *,
        profile_id: str,
        choices: list[dict[str, str]],
        replace: bool,
    ) -> dict[str, object]:
        self.completed_with = {
            "profile_id": profile_id,
            "choices": choices,
            "replace": replace,
        }
        return {
            "profile": _profile(profile_id),
            "cold_start": {
                "questions_answered": 4,
                "total_questions": 6,
                "completed": True,
                "confidence": 0.8,
                "weights": _weights(),
                "transport_affinity": {"train": 0.5},
                "signals": [],
            },
            "learned_signals": ["Предпочитает более быстрые поездки"],
        }

    async def get_profile(self, profile_id: str) -> dict[str, object] | None:
        return None


def _question(index: int) -> dict[str, object]:
    def option(side: str) -> dict[str, object]:
        return {
            "id": f"question-{index}:{side}",
            "title": "Дешевле" if side == "left" else "Быстрее",
            "subtitle": "Тестовый вариант",
            "total_price": 4900 if side == "left" else 10500,
            "duration_minutes": 720 if side == "left" else 110,
            "transfers": 0,
            "transport": "train" if side == "left" else "flight",
            "hotel_rating": None,
        }

    return {
        "id": f"question-{index}",
        "prompt": "Что выберете?",
        "left": option("left"),
        "right": option("right"),
        "targets": ["price", "duration"],
    }


def _weights() -> dict[str, float]:
    return {"price": 0.8, "duration": 0.7, "transfers": 0.2, "hotel_quality": 0.1}


def _profile(profile_id: str) -> dict[str, object]:
    now = datetime.now(UTC).isoformat()
    return {
        "profile_id": profile_id,
        "version": 2,
        "interactions": 4,
        "weights": _weights(),
        "transport_affinity": {"train": 0.5},
        "action_counts": {"cold_start": 4},
        "cold_start_completed": True,
        "cold_start_answers": 4,
        "cold_start_confidence": 0.8,
        "cold_start_completed_at": now,
        "updated_at": now,
    }


def _sign_in(client: TestClient) -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Анна",
            "email": "preferences@example.com",
            "password": "very-safe-password",
        },
    )
    assert response.status_code == 201
    return response.json()["user"]["id"]


def test_preferences_require_authenticated_user(client: TestClient) -> None:
    response = client.get("/api/v1/preferences/cold-start/questions")

    assert response.status_code == 401


def test_cold_start_uses_authenticated_user_as_profile_id(client: TestClient) -> None:
    fake = FakeTripRescueClient()
    app.dependency_overrides[get_trip_rescue_client] = lambda: fake
    try:
        user_id = _sign_in(client)
        questions = client.get("/api/v1/preferences/cold-start/questions?limit=4")
        assert questions.status_code == 200

        choices = [
            {
                "question_id": question["id"],
                "selected_option_id": question["left"]["id"],
            }
            for question in questions.json()["questions"]
        ]
        completed = client.post(
            "/api/v1/preferences/cold-start/complete",
            json={"choices": choices},
        )

        assert completed.status_code == 200
        assert completed.json()["profile"]["profile_id"] == user_id
        assert fake.completed_with is not None
        assert fake.completed_with["profile_id"] == user_id
    finally:
        app.dependency_overrides.pop(get_trip_rescue_client, None)
