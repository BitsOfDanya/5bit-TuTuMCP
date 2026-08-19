from typing import Any

import httpx

from app.domain.travel import TravelService, TripDetails


class ConstraintNegotiatorClient:
    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    async def negotiate(self, trip: TripDetails) -> dict[str, Any]:
        if trip.service_type is TravelService.HOTEL:
            return {"status": "skipped", "reason": "Hotel-only trips are not supported."}
        if not all(
            [
                trip.origin,
                trip.destination,
                trip.start_date,
                trip.end_date,
                trip.passengers,
            ]
        ):
            return {
                "status": "skipped",
                "reason": "A complete round trip is required for constraint negotiation.",
            }

        preferred_transport = [trip.service_type.value] if trip.service_type else []
        payload = {
            "trip": {
                "origin": trip.origin,
                "destination": trip.destination,
                "outbound_date": trip.start_date.isoformat(),
                "return_date": trip.end_date.isoformat(),
                "outbound_after": (
                    trip.preferred_time.isoformat() if trip.preferred_time else None
                ),
                "travelers": trip.passengers,
                "budget": trip.budget,
                "preferred_transport": preferred_transport,
            }
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/api/v1/negotiator/from-spec",
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
