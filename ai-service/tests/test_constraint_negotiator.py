from datetime import date, time
from typing import Any

import pytest

from app.domain.travel import TravelService, TripDetails
from app.integrations.constraint_negotiator.client import ConstraintNegotiatorClient


class FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return {"status": "success", "journeys": [{"id": "journey-1"}]}


class FakeAsyncClient:
    payload: dict[str, Any] | None = None

    def __init__(self, **_: Any) -> None:
        pass

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        return None

    async def post(self, _: str, *, json: dict[str, Any]) -> FakeResponse:
        FakeAsyncClient.payload = json
        return FakeResponse()


@pytest.mark.asyncio
async def test_maps_complete_round_trip_to_constraint_negotiator(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.integrations.constraint_negotiator.client.httpx.AsyncClient",
        FakeAsyncClient,
    )
    client = ConstraintNegotiatorClient("http://negotiator:8010", 10)
    result = await client.negotiate(
        TripDetails(
            service_type=TravelService.TRAIN,
            origin="Москва",
            destination="Казань",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 5),
            preferred_time=time(10, 30),
            passengers=2,
            budget=30_000,
        )
    )
    assert result["status"] == "success"
    assert FakeAsyncClient.payload == {
        "trip": {
            "origin": "Москва",
            "destination": "Казань",
            "outbound_date": "2026-09-01",
            "return_date": "2026-09-05",
            "outbound_after": "10:30:00",
            "travelers": 2,
            "budget": 30_000,
            "preferred_transport": ["train"],
        }
    }


@pytest.mark.asyncio
async def test_skips_incomplete_one_way_trip() -> None:
    client = ConstraintNegotiatorClient("http://negotiator:8010", 10)
    result = await client.negotiate(
        TripDetails(
            service_type=TravelService.BUS,
            origin="Москва",
            destination="Тула",
            start_date=date(2026, 9, 1),
            passengers=1,
        )
    )
    assert result["status"] == "skipped"
