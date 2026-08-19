import json
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

import httpx

from app.schemas import HotelOffer, TransportOffer, TripCandidates, TripIntent


class TripOfferProvider(Protocol):
    def search(self, intent: TripIntent) -> TripCandidates: ...


class TutuMcpError(RuntimeError):
    pass


class TutuMcpProvider:
    """Small Streamable HTTP MCP client for the public, read-only Tutu endpoint."""

    def __init__(
        self,
        endpoint: str = "https://mcp.tutu.ru/mcp",
        timeout_seconds: float = 30,
    ) -> None:
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds

    def search(self, intent: TripIntent) -> TripCandidates:
        transport_payload = self._call_tool(
            "search_avia",
            {
                "origin": intent.origin,
                "destination": intent.destination,
                "departure_date": intent.departure_date.isoformat(),
                "return_date": intent.return_date.isoformat(),
                "adults": intent.adults,
                "direct_only": intent.direct_only,
                "page_size": 5,
                "sort": "price_asc",
                "view": "compact",
            },
        )
        hotel_payload = self._call_tool(
            "search_hotels",
            {
                "city_name": intent.destination,
                "check_in": intent.departure_date.isoformat(),
                "check_out": intent.return_date.isoformat(),
                "adults": intent.adults,
                "min_rating": intent.hotel_rating_min or None,
                "page_size": 5,
                "view": "compact",
            },
        )
        return TripCandidates(
            transport=_normalize_avia(transport_payload),
            hotels=_normalize_hotels(hotel_payload),
        )

    def _call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        try:
            response = httpx.post(
                self.endpoint,
                json=request,
                headers={"Accept": "application/json, text/event-stream"},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            envelope = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise TutuMcpError("Tutu MCP is unavailable.") from exc

        if envelope.get("error"):
            raise TutuMcpError(str(envelope["error"]))
        result = envelope.get("result", {})
        if result.get("isError"):
            raise TutuMcpError(_content_text(result) or f"{name} failed.")

        content = _content_text(result)
        if not content:
            raise TutuMcpError(f"{name} returned no JSON content.")
        try:
            payload = json.loads(content)
        except ValueError as exc:
            raise TutuMcpError(f"{name} returned malformed JSON.") from exc
        if not isinstance(payload, dict):
            raise TutuMcpError(f"{name} returned an unexpected payload.")
        return payload


class DemoTripOfferProvider:
    def search(self, intent: TripIntent) -> TripCandidates:
        outbound_base = datetime.combine(
            intent.departure_date,
            datetime.min.time(),
            tzinfo=UTC,
        )
        return_base = datetime.combine(
            intent.return_date,
            datetime.min.time(),
            tzinfo=UTC,
        )
        transport = [
            TransportOffer(
                id="demo-flight-early",
                price=18_900,
                departure_at=outbound_base + timedelta(hours=7),
                arrival_at=outbound_base + timedelta(hours=9),
                return_departure_at=return_base + timedelta(hours=19),
                return_arrival_at=return_base + timedelta(hours=21),
                duration_minutes=240,
                transfers=0,
                carriers=["Demo Air"],
                search_results_url="https://avia.tutu.ru/",
            ),
            TransportOffer(
                id="demo-flight-comfort",
                price=21_400,
                departure_at=outbound_base + timedelta(hours=11),
                arrival_at=outbound_base + timedelta(hours=13),
                return_departure_at=return_base + timedelta(hours=21),
                return_arrival_at=return_base + timedelta(hours=23),
                duration_minutes=240,
                transfers=0,
                carriers=["Comfort Demo"],
                search_results_url="https://avia.tutu.ru/",
            ),
            TransportOffer(
                id="demo-flight-transfer",
                price=16_700,
                departure_at=outbound_base + timedelta(hours=9),
                arrival_at=outbound_base + timedelta(hours=14),
                return_departure_at=return_base + timedelta(hours=16),
                return_arrival_at=return_base + timedelta(hours=22),
                duration_minutes=660,
                transfers=2,
                carriers=["Budget Demo"],
                search_results_url="https://avia.tutu.ru/",
            ),
        ]
        hotels = [
            HotelOffer(
                id="demo-hotel-center",
                name="Отель в центре",
                price_total=15_200,
                rating=9.1,
                checkout_url="https://hotel.tutu.ru/",
            ),
            HotelOffer(
                id="demo-hotel-comfort",
                name="Комфорт у набережной",
                price_total=13_400,
                rating=8.7,
                checkout_url="https://hotel.tutu.ru/",
            ),
            HotelOffer(
                id="demo-hotel-budget",
                name="Городской отель",
                price_total=9_800,
                rating=7.5,
                checkout_url="https://hotel.tutu.ru/",
            ),
        ]
        return TripCandidates(transport=transport, hotels=hotels)


def _content_text(result: dict[str, Any]) -> str | None:
    for item in result.get("content", []):
        if item.get("type") == "text" and isinstance(item.get("text"), str):
            return item["text"]
    return None


def _normalize_avia(payload: dict[str, Any]) -> list[TransportOffer]:
    normalized: list[TransportOffer] = []
    for offer in payload.get("offers", []):
        try:
            legs = offer["legs"]
            outbound = legs[0]
            inbound = legs[-1]
            transfers = sum(max(0, len(leg.get("segments", [])) - 1) for leg in legs)
            normalized.append(
                TransportOffer(
                    id=str(offer["offer_id"]),
                    price=round(float(offer["price"]["amount"])),
                    currency=str(offer["price"].get("currency", "RUB")),
                    departure_at=offer["departure_at"],
                    arrival_at=offer["arrival_at"],
                    return_departure_at=offer["return_departure_at"],
                    return_arrival_at=offer["return_arrival_at"],
                    duration_minutes=sum(
                        int(leg.get("duration_min", 0)) for leg in (outbound, inbound)
                    ),
                    transfers=transfers,
                    carriers=[str(carrier) for carrier in offer.get("carriers", [])],
                    search_results_url=offer.get("search_results_url"),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return normalized


def _normalize_hotels(payload: dict[str, Any]) -> list[HotelOffer]:
    normalized: list[HotelOffer] = []
    for hotel in payload.get("hotels", []):
        try:
            best_offer = hotel["best_offer"]
            normalized.append(
                HotelOffer(
                    id=str(hotel["hotel_id"]),
                    name=str(hotel["name"]),
                    price_total=round(float(best_offer["price"]["amount"])),
                    currency=str(best_offer["price"].get("currency", "RUB")),
                    rating=float(hotel.get("rating") or 0),
                    checkout_url=best_offer.get("checkout_url") or hotel.get("checkout_url"),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return normalized
