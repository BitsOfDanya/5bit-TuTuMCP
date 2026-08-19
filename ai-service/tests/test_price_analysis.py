from datetime import date, time
from typing import Any

import pytest

from app.agent.tools.price_analysis import PurchaseTimingAnalyzer
from app.domain.travel import TravelService, TripDetails


def trip() -> TripDetails:
    return TripDetails(
        service_type=TravelService.TRAIN,
        origin="Москва",
        destination="Казань",
        start_date=date(2026, 9, 1),
        preferred_time=time(10, 0),
        passengers=1,
        budget=20_000,
    )


def tracking_response(*, history_points: int = 2) -> dict[str, Any]:
    return {
        "id": "tracking-1",
        "intent": {
            "origin": "Москва",
            "destination": "Казань",
            "departure_date": "2026-09-01",
            "return_date": None,
        },
        "active": True,
        "last_checked_at": "2026-08-19T12:00:00Z",
        "summary": {
            "current_price": 9_500,
            "minimum_price": 9_000,
            "average_price": 9_250,
            "difference_from_min": 500,
        },
        "recommendation": {
            "status": "GOOD_VALUE",
            "message": "Цена выглядит разумно относительно накопленной истории.",
        },
        "history": [{"total_price": 9_000}] * history_points,
    }


class FakeTracker:
    def __init__(self, items: list[dict[str, Any]]) -> None:
        self.items = items
        self.created_payload: dict[str, Any] | None = None
        self.refreshed_id: str | None = None

    async def list(self) -> list[dict[str, Any]]:
        return self.items

    async def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.created_payload = payload
        return tracking_response(history_points=1)

    async def refresh(self, tracking_id: str) -> dict[str, Any]:
        self.refreshed_id = tracking_id
        return tracking_response()


class FakeNegotiator:
    def __init__(self) -> None:
        self.calls = 0

    async def negotiate(self, _: TripDetails) -> dict[str, Any]:
        self.calls += 1
        return {
            "status": "success",
            "trip_spec": {
                "origin": "Москва",
                "destination": "Казань",
                "outbound_date": "2026-09-01",
                "return_date": None,
                "travelers": 1,
                "budget": 20_000,
                "max_transfers": None,
            },
            "options": [
                {
                    "id": "train-1",
                    "kind": "journey",
                    "title": "Москва — Казань",
                    "total_price": 9_500,
                    "currency": "RUB",
                    "outbound": {
                        "mode": "train",
                        "origin": "Москва",
                        "destination": "Казань",
                        "departure": "2026-09-01T10:00:00+03:00",
                        "arrival": "2026-09-01T21:00:00+03:00",
                        "price": 9_500,
                        "duration_minutes": 660,
                        "transfers": 0,
                        "carrier": "ФПК",
                    },
                    "action_url": "https://www.tutu.ru/poezda/",
                }
            ],
        }


@pytest.mark.asyncio
async def test_reuses_matching_tracking_and_returns_compact_recommendation() -> None:
    tracker = FakeTracker([tracking_response()])
    negotiator = FakeNegotiator()
    analyzer = PurchaseTimingAnalyzer(negotiator, tracker)  # type: ignore[arg-type]

    result = await analyzer.analyze(trip())

    assert result["status"] == "success"
    assert result["source"] == "smart_trip_tracker"
    assert result["recommendation"]["status"] == "GOOD_VALUE"
    assert result["prices"]["current"] == 9_500
    assert result["history_points"] == 2
    assert tracker.refreshed_id == "tracking-1"
    assert negotiator.calls == 0


@pytest.mark.asyncio
async def test_creates_tracking_from_real_option_when_history_does_not_exist() -> None:
    tracker = FakeTracker([])
    negotiator = FakeNegotiator()
    analyzer = PurchaseTimingAnalyzer(negotiator, tracker)  # type: ignore[arg-type]

    result = await analyzer.analyze(trip())

    assert result["status"] == "success"
    assert result["created"] is True
    assert negotiator.calls == 1
    assert tracker.created_payload is not None
    assert tracker.created_payload["journeys"][0]["inbound"] is None
    assert tracker.refreshed_id == "tracking-1"
