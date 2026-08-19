from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.main import app, get_service
from app.provider import DemoTripOfferProvider
from app.service import TripTrackingService


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    service = TripTrackingService(DemoTripOfferProvider())
    app.dependency_overrides[get_service] = lambda: service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_create_simulate_and_stop_tracking(client: TestClient) -> None:
    created = client.post(
        "/api/v1/trips",
        json={
            "origin": "Москва",
            "destination": "Казань",
            "departure_date": "2026-09-10",
            "return_date": "2026-09-13",
            "adults": 1,
            "budget": 45000,
            "direct_only": True,
            "hotel_rating_min": 8,
        },
    )

    assert created.status_code == 201
    tracking_id = created.json()["id"]
    assert created.json()["recommendation"]["status"] == "COLLECTING_DATA"

    simulated = client.post(f"/api/v1/trips/{tracking_id}/simulate")
    assert simulated.status_code == 200
    assert len(simulated.json()["history"]) == 2

    stopped = client.delete(f"/api/v1/trips/{tracking_id}")
    assert stopped.status_code == 200
    assert stopped.json()["active"] is False

    refresh = client.post(f"/api/v1/trips/{tracking_id}/refresh")
    assert refresh.status_code == 409
