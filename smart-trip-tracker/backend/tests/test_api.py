from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.main import app, get_service
from app.provider import DemoTripOfferProvider, TutuMcpError
from app.schemas import TripCandidates, TripIntent
from app.service import TripTrackingService


def trip_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "origin": "Москва",
        "destination": "Казань",
        "departure_date": "2026-09-10",
        "return_date": "2026-09-13",
        "adults": 1,
        "budget": 45_000,
        "direct_only": True,
        "hotel_rating_min": 8,
    }
    return payload | overrides


class UnavailableProvider:
    def search(self, _intent: TripIntent) -> TripCandidates:
        raise TutuMcpError("Tutu MCP is unavailable.")


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
        json=trip_payload(),
    )

    assert created.status_code == 201
    tracking_id = created.json()["id"]
    assert created.json()["recommendation"]["status"] == "COLLECTING_DATA"

    simulated = client.post(f"/api/v1/trips/{tracking_id}/simulate?scenario=spike")
    assert simulated.status_code == 200
    assert len(simulated.json()["history"]) == 2
    assert simulated.json()["recommendation"]["status"] == "WAIT"

    invalid_scenario = client.post(f"/api/v1/trips/{tracking_id}/simulate?scenario=unknown")
    assert invalid_scenario.status_code == 422

    stopped = client.delete(f"/api/v1/trips/{tracking_id}")
    assert stopped.status_code == 200
    assert stopped.json()["active"] is False

    refresh = client.post(f"/api/v1/trips/{tracking_id}/refresh")
    assert refresh.status_code == 409


def test_returns_422_when_no_complete_trip_matches(client: TestClient) -> None:
    response = client.post(
        "/api/v1/trips",
        json=trip_payload(hotel_rating_min=10),
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "No complete trip combinations were found."


def test_returns_502_when_tutu_mcp_is_unavailable(client: TestClient) -> None:
    app.dependency_overrides[get_service] = lambda: TripTrackingService(UnavailableProvider())

    response = client.post("/api/v1/trips", json=trip_payload())

    assert response.status_code == 502
    assert response.json()["detail"] == "Tutu MCP is unavailable."
