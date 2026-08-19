from functools import lru_cache
from typing import Any

import httpx

from app.domain.travel import TravelService, TripDetails


class ConstraintNegotiatorUnavailable(RuntimeError):
    pass


class ConstraintNegotiatorClient:
    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    async def negotiate(self, trip: TripDetails) -> dict[str, Any]:
        if not all([trip.service_type, trip.destination, trip.start_date, trip.passengers]):
            return {
                "status": "skipped",
                "reason": "Complete product search fields are required.",
            }
        if trip.service_type is not TravelService.HOTEL and not trip.origin:
            return {"status": "skipped", "reason": "Origin is required for transport search."}
        if trip.service_type is TravelService.HOTEL and not trip.end_date:
            return {"status": "skipped", "reason": "Check-out date is required for hotel search."}

        payload = {
            "service_type": trip.service_type.value,
            "origin": trip.origin,
            "destination": trip.destination,
            "start_date": trip.start_date.isoformat(),
            "end_date": trip.end_date.isoformat() if trip.end_date else None,
            "preferred_time": trip.preferred_time.isoformat() if trip.preferred_time else None,
            "travelers": trip.passengers,
            "budget": trip.budget,
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/api/v1/negotiator/products/search",
                    json=payload,
                )
                response.raise_for_status()
        except (httpx.HTTPError, ValueError) as exc:
            return {
                "status": "unavailable",
                "reason": "Constraint negotiator is temporarily unavailable.",
                "error_type": type(exc).__name__,
            }
        return response.json()

    async def health(self) -> dict[str, str]:
        try:
            async with httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout) as client:
                response = await client.get("/health")
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ConstraintNegotiatorUnavailable("Constraint negotiator is unavailable.") from exc
        if not isinstance(payload, dict) or payload.get("status") != "ok":
            raise ConstraintNegotiatorUnavailable("Constraint negotiator is not healthy.")
        return {
            "status": "ok",
            "service": str(payload.get("service", "constraint-negotiator")),
        }


@lru_cache
def get_constraint_negotiator_client() -> ConstraintNegotiatorClient:
    from app.core.config import get_settings

    settings = get_settings()
    return ConstraintNegotiatorClient(
        settings.constraint_negotiator_url,
        settings.constraint_negotiator_timeout_seconds,
    )


def compact_negotiation_result(payload: dict[str, Any], limit: int = 3) -> dict[str, Any]:
    """Keep the useful search summary out of large Tutu checkout payloads."""
    result: dict[str, Any] = {
        "status": payload.get("status", "no_options"),
        "journeys": [
            _compact_journey(journey)
            for journey in payload.get("journeys", [])[:limit]
            if isinstance(journey, dict)
        ],
        "alternatives": [
            _compact_alternative(alternative)
            for alternative in payload.get("alternatives", [])[:limit]
            if isinstance(alternative, dict)
        ],
    }
    if isinstance(payload.get("trip_spec"), dict):
        result["trip_spec"] = payload["trip_spec"]
    return result


def _compact_alternative(alternative: dict[str, Any]) -> dict[str, Any]:
    compact = {
        key: alternative[key]
        for key in ("id", "kind", "changes", "score", "new_trip_spec", "summary")
        if key in alternative
    }
    if isinstance(alternative.get("journey"), dict):
        compact["journey"] = _compact_journey(alternative["journey"])
    return compact


def _compact_journey(journey: dict[str, Any]) -> dict[str, Any]:
    compact = {
        key: journey[key]
        for key in ("id", "total_price", "transport_price", "hotel_price")
        if key in journey
    }
    for direction in ("outbound", "inbound"):
        segment = journey.get(direction)
        if isinstance(segment, dict):
            compact[direction] = {
                key: segment[key]
                for key in (
                    "id",
                    "mode",
                    "origin",
                    "destination",
                    "departure",
                    "arrival",
                    "price",
                    "currency",
                    "duration_minutes",
                    "transfers",
                    "carrier",
                    "voyage_no",
                    "rating",
                    "review_count",
                    "booking_url",
                    "search_results_url",
                )
                if key in segment
            }
    hotel = journey.get("hotel")
    if isinstance(hotel, dict):
        compact["hotel"] = {
            key: hotel[key]
            for key in (
                "id",
                "name",
                "price",
                "currency",
                "stars",
                "rating",
                "address",
                "room_name",
                "check_in",
                "check_out",
                "nights",
                "booking_url",
                "photo_url",
            )
            if key in hotel
        }
    return compact
