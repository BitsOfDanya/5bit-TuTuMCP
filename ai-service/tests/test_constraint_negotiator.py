from datetime import date, time
from typing import Any

import pytest

from app.domain.travel import TravelService, TripDetails
from app.integrations.constraint_negotiator.client import (
    ConstraintNegotiatorClient,
    compact_negotiation_result,
)


class FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return {"status": "success", "options": [{"id": "journey-1"}]}


class FakeAsyncClient:
    payload: dict[str, Any] | None = None
    url: str | None = None

    def __init__(self, **_: Any) -> None:
        pass

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        return None

    async def post(self, url: str, *, json: dict[str, Any]) -> FakeResponse:
        FakeAsyncClient.url = url
        FakeAsyncClient.payload = json
        return FakeResponse()


@pytest.mark.asyncio
async def test_maps_round_trip_to_public_negotiation_endpoint(monkeypatch) -> None:
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
    assert FakeAsyncClient.url == "http://negotiator:8010/api/v1/negotiator/from-spec/public"
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
async def test_searches_complete_one_way_trip(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.integrations.constraint_negotiator.client.httpx.AsyncClient",
        FakeAsyncClient,
    )
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
    assert result["status"] == "success"
    assert FakeAsyncClient.url == "http://negotiator:8010/api/v1/negotiator/products/search"
    assert FakeAsyncClient.payload["service_type"] == "bus"
    assert FakeAsyncClient.payload["end_date"] is None
    assert result["trip_spec"] == {
        "origin": "Москва",
        "destination": "Тула",
        "outbound_date": "2026-09-01",
        "return_date": None,
        "travelers": 1,
        "budget": None,
        "max_transfers": None,
    }


def test_compacts_large_tutu_references_before_returning_to_agent() -> None:
    payload = {
        "status": "success",
        "trip_spec": {"origin": "Москва", "destination": "Казань"},
        "journeys": [
            {
                "id": "journey-1",
                "total_price": 20_000,
                "outbound": {
                    "id": "out-1",
                    "mode": "train",
                    "departure": "2026-09-01T10:00:00+03:00",
                    "checkout_ref": {"large": "payload" * 10_000},
                },
                "inbound": {
                    "id": "back-1",
                    "mode": "train",
                    "details_ref": {"large": "payload" * 10_000},
                },
            }
        ],
        "alternatives": [],
    }

    compact = compact_negotiation_result(payload)

    assert compact["status"] == "success"
    assert compact["journeys"][0]["outbound"] == {
        "id": "out-1",
        "mode": "train",
        "departure": "2026-09-01T10:00:00+03:00",
    }
    assert "checkout_ref" not in str(compact)
    assert "details_ref" not in str(compact)
