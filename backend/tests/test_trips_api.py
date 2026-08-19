import asyncio
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.database import initialize_database
from app.db import get_session
from app.main import app
from app.trip_rescue_client import get_trip_rescue_client


class FakeTripRescueClient:
    def __init__(self) -> None:
        self.what_if_profile_id: str | None = None

    async def record_preference_feedback(self, **_: object) -> dict[str, object]:
        return {"status": "learned"}

    async def what_if_from_text(
        self,
        *,
        trip: dict[str, object],
        journey: dict[str, object],
        message: str,
        profile_id: str,
    ) -> dict[str, object]:
        self.what_if_profile_id = profile_id
        return {"simulation": True, "status": "alternatives_found", "candidates": []}


@pytest.fixture
def client() -> Generator[tuple[TestClient, FakeTripRescueClient], None, None]:
    asyncio.run(initialize_database())
    auth_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(auth_engine)

    def override_session() -> Generator[Session, None, None]:
        with Session(auth_engine) as session:
            yield session

    fake = FakeTripRescueClient()
    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_trip_rescue_client] = lambda: fake
    with TestClient(app) as test_client:
        yield test_client, fake
    app.dependency_overrides.clear()


def test_accepts_trip_and_runs_non_committing_whatif(
    client: tuple[TestClient, FakeTripRescueClient],
) -> None:
    test_client, fake = client
    registered = test_client.post(
        "/api/v1/auth/register",
        json={
            "name": "Иван",
            "email": "trip-owner@example.com",
            "password": "very-safe-password",
        },
    )
    user_id = registered.json()["user"]["id"]
    payload = _accepted_trip_payload()

    accepted = test_client.put("/api/v1/trips/current", json=payload)
    simulated = test_client.post(
        "/api/v1/trips/current/what-if",
        json={"message": "А что если вернуться до 10?"},
    )
    current = test_client.get("/api/v1/trips/current")

    assert accepted.status_code == 200
    assert simulated.status_code == 200
    assert simulated.json()["result"]["simulation"] is True
    assert fake.what_if_profile_id == user_id
    assert current.json()["journey"]["id"] == "journey-1"


def _accepted_trip_payload() -> dict[str, object]:
    return {
        "trip": {
            "origin": "Москва",
            "destination": "Казань",
            "outbound_date": "2026-09-01",
            "return_date": "2026-09-05",
            "travelers": 1,
            "budget": 25000,
            "hard_constraints": ["budget"],
        },
        "journey": {
            "id": "journey-1",
            "total_price": 18900,
            "outbound": {
                "mode": "train",
                "origin": "Москва",
                "destination": "Казань",
                "departure": "2026-09-01T10:00:00+03:00",
                "arrival": "2026-09-01T21:30:00+03:00",
                "price": 9500,
            },
            "inbound": {
                "mode": "train",
                "origin": "Казань",
                "destination": "Москва",
                "departure": "2026-09-05T18:00:00+03:00",
                "arrival": "2026-09-06T05:30:00+03:00",
                "price": 9400,
            },
        },
    }
