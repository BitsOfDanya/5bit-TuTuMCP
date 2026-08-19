from datetime import date

import pytest

from app.api.schemas import ProductSearchRequest
from app.models.journey import HotelOption
from app.search.products import ProductSearchService


class FakeTutuClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def call_tool(self, *, name: str, arguments: dict) -> dict:
        self.calls.append((name, arguments))
        if name == "create_checkout_link":
            return {
                "checkout_url": f"https://www.tutu.ru/{arguments['transport']}/checkout"
            }
        transport = {
            "search_rail": "railway",
            "search_avia": "avia",
            "search_bus": "bus",
        }[name]
        return {
            "offers": [
                {
                    "offer_id": f"{transport}-1",
                    "transport": transport,
                    "departure_at": "2026-09-01T10:00:00+03:00",
                    "arrival_at": "2026-09-01T12:00:00+03:00",
                    "duration_min": 120,
                    "segments_count": 1,
                    "price": {"amount": 5000, "currency": "RUB"},
                    "legs": [
                        {
                            "from": "Москва",
                            "to": "Казань",
                            "segments": [{"carrier": "Тест", "voyage_no": "T1"}],
                        }
                    ],
                    "checkout_ref": {"transport": transport},
                }
            ]
        }


class FakeHotelProvider:
    async def search_options(self, **_: object) -> list[HotelOption]:
        return [
            HotelOption(
                id="hotel-1",
                name="Отель у Кремля",
                price=8000,
                check_in=date(2026, 9, 1),
                check_out=date(2026, 9, 3),
                nights=2,
                booking_url="https://hotel.tutu.ru/offers/details?id=1",
            )
        ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("service_type", "tool_name", "mode"),
    [
        ("train", "search_rail", "train"),
        ("flight", "search_avia", "flight"),
        ("bus", "search_bus", "bus"),
    ],
)
async def test_transport_search_uses_dedicated_mcp_tool(
    service_type: str,
    tool_name: str,
    mode: str,
) -> None:
    client = FakeTutuClient()
    service = ProductSearchService(client=client, hotel_provider=FakeHotelProvider())

    result = await service.search(
        ProductSearchRequest(
            service_type=service_type,
            origin="Москва",
            destination="Казань",
            start_date="2026-09-01",
            travelers=1,
            budget=20_000,
        )
    )

    assert result.status == "success"
    assert result.options[0].outbound is not None
    assert result.options[0].outbound.mode.value == mode
    assert (
        result.options[0].action_url
        == f"https://www.tutu.ru/{client.calls[1][1]['transport']}/checkout"
    )
    assert client.calls[0][0] == tool_name


@pytest.mark.asyncio
async def test_flight_search_passes_return_date_to_mcp() -> None:
    client = FakeTutuClient()
    service = ProductSearchService(client=client, hotel_provider=FakeHotelProvider())

    await service.search(
        ProductSearchRequest(
            service_type="flight",
            origin="Москва",
            destination="Казань",
            start_date="2026-09-01",
            end_date="2026-09-05",
            travelers=1,
        )
    )

    assert client.calls[0][1]["return_date"] == "2026-09-05"


@pytest.mark.asyncio
async def test_hotel_search_does_not_require_origin() -> None:
    service = ProductSearchService(
        client=FakeTutuClient(),
        hotel_provider=FakeHotelProvider(),
    )

    result = await service.search(
        ProductSearchRequest(
            service_type="hotel",
            destination="Казань",
            start_date="2026-09-01",
            end_date="2026-09-03",
            travelers=2,
            budget=10_000,
        )
    )

    assert result.status == "success"
    assert result.options[0].hotel is not None
    assert result.options[0].hotel.name == "Отель у Кремля"
    assert result.options[0].outbound is None
