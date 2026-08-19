from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.main import app, get_service
from app.provider import DemoTripOfferProvider, TutuMcpError
from app.schemas import TripCandidates, TripIntent
from app.service import TripTrackingService


def trip_payload(
    *,
    total_price: int = 34_800,
    **overrides: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "status": "success",
        "trip_spec": {
            "origin": "Москва",
            "destination": "Казань",
            "outbound_date": "2026-09-10",
            "return_date": "2026-09-13",
            "travelers": 1,
            "budget": 45_000,
            "max_transfers": 0,
        },
        "journeys": [
            {
                "id": "tutu:test-journey",
                "total_price": total_price,
                "transport_price": 21_400,
                "hotel_price": total_price - 21_400,
                "outbound": {
                    "mode": "flight",
                    "origin": "Москва",
                    "destination": "Казань",
                    "departure": "2026-09-10T11:00:00+03:00",
                    "arrival": "2026-09-10T12:30:00+03:00",
                    "price": 10_700,
                    "duration_minutes": 90,
                    "transfers": 0,
                    "carrier": "Demo Air",
                    "booking_url": None,
                },
                "inbound": {
                    "mode": "flight",
                    "origin": "Казань",
                    "destination": "Москва",
                    "departure": "2026-09-13T20:00:00+03:00",
                    "arrival": "2026-09-13T21:30:00+03:00",
                    "price": 10_700,
                    "duration_minutes": 90,
                    "transfers": 0,
                    "carrier": "Demo Air",
                    "booking_url": None,
                },
                "hotel": {
                    "name": "Комфорт у набережной",
                    "price": total_price - 21_400,
                    "rating": 8.7,
                    "booking_url": None,
                },
            }
        ],
        "alternatives": [],
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

    observed = client.post(
        f"/api/v1/trips/{tracking_id}/observations",
        json=trip_payload(total_price=32_000),
    )
    assert observed.status_code == 200
    assert len(observed.json()["history"]) == 2
    assert observed.json()["summary"]["current_price"] == 32_000

    simulated = client.post(f"/api/v1/trips/{tracking_id}/simulate?scenario=spike")
    assert simulated.status_code == 200
    assert len(simulated.json()["history"]) == 3
    assert simulated.json()["recommendation"]["status"] == "WAIT"

    invalid_scenario = client.post(f"/api/v1/trips/{tracking_id}/simulate?scenario=unknown")
    assert invalid_scenario.status_code == 422

    stopped = client.delete(f"/api/v1/trips/{tracking_id}")
    assert stopped.status_code == 200
    assert stopped.json()["active"] is False

    refresh = client.post(f"/api/v1/trips/{tracking_id}/refresh")
    assert refresh.status_code == 409


def test_returns_422_when_negotiator_has_no_options(client: TestClient) -> None:
    response = client.post(
        "/api/v1/trips",
        json=trip_payload(status="no_options", journeys=[]),
    )

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "Constraint Negotiator did not return a trackable journey."
    )

def test_creates_tracking_from_best_negotiation_alternative(
    client: TestClient,
) -> None:
    payload = trip_payload()
    trip_spec = payload["trip_spec"]
    journey = payload["journeys"][0]  # type: ignore[index]
    payload.update(
        {
            "status": "negotiation_required",
            "journeys": [],
            "alternatives": [
                {
                    "id": "relax-test",
                    "kind": "single",
                    "score": 0.2,
                    "new_trip_spec": trip_spec,
                    "journey": journey,
                }
            ],
        }
    )

    response = client.post("/api/v1/trips", json=payload)

    assert response.status_code == 201
    assert response.json()["summary"]["current_price"] == 34_800


def test_returns_502_when_tutu_mcp_is_unavailable(client: TestClient) -> None:
    unavailable_service = TripTrackingService(UnavailableProvider())
    app.dependency_overrides[get_service] = lambda: unavailable_service
    created = client.post("/api/v1/trips", json=trip_payload())
    tracking_id = created.json()["id"]

    response = client.post(f"/api/v1/trips/{tracking_id}/refresh")

    assert response.status_code == 502
    assert response.json()["detail"] == "Tutu MCP is unavailable."
