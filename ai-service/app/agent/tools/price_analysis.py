from typing import Any

from app.agent.search_options import build_search_options
from app.domain.travel import TravelService, TripDetails
from app.integrations.constraint_negotiator.client import ConstraintNegotiatorClient
from app.integrations.smart_trip_tracker.client import (
    SmartTripTrackerClient,
    SmartTripTrackerUnavailable,
)


class PurchaseTimingAnalyzer:
    def __init__(
        self,
        negotiator: ConstraintNegotiatorClient,
        tracker: SmartTripTrackerClient,
    ) -> None:
        self._negotiator = negotiator
        self._tracker = tracker

    async def analyze(self, trip: TripDetails) -> dict[str, Any]:
        if trip.service_type is TravelService.HOTEL:
            return {
                "status": "unsupported",
                "reason": "Purchase timing analysis currently supports transport tickets.",
            }
        if not trip.origin or not trip.destination or not trip.start_date:
            return {
                "status": "incomplete",
                "reason": "Origin, destination, and departure date are required.",
            }

        try:
            tracking = self._find_matching(await self._tracker.list(), trip)
            created = tracking is None
            if tracking is None:
                tracking = await self._create_tracking(trip)
                if tracking is None:
                    return {
                        "status": "no_options",
                        "reason": "No trackable ticket was found for this trip.",
                    }

            refreshed = True
            try:
                tracking = await self._tracker.refresh(str(tracking["id"]))
            except SmartTripTrackerUnavailable:
                refreshed = False
            return self._compact_result(tracking, created=created, refreshed=refreshed)
        except SmartTripTrackerUnavailable as exc:
            return {"status": "unavailable", "reason": str(exc)}

    async def _create_tracking(self, trip: TripDetails) -> dict[str, Any] | None:
        negotiation = await self._negotiator.negotiate(trip)
        options = [
            option
            for option in build_search_options(negotiation, None)
            if option.tracking_payload is not None
        ]
        if not options:
            return None
        option = min(options, key=lambda item: item.total_price)
        payload = option.tracking_payload
        if payload is None:
            return None
        return await self._tracker.create(payload.model_dump(mode="json"))

    @staticmethod
    def _find_matching(
        trackings: list[dict[str, Any]],
        trip: TripDetails,
    ) -> dict[str, Any] | None:
        expected_return = trip.end_date.isoformat() if trip.end_date else None
        matches = []
        for tracking in trackings:
            intent = tracking.get("intent")
            if not isinstance(intent, dict) or not tracking.get("active"):
                continue
            if (
                str(intent.get("origin", "")).casefold() == trip.origin.casefold()
                and str(intent.get("destination", "")).casefold()
                == trip.destination.casefold()
                and intent.get("departure_date") == trip.start_date.isoformat()
                and intent.get("return_date") == expected_return
            ):
                matches.append(tracking)
        if not matches:
            return None
        return max(matches, key=lambda item: str(item.get("last_checked_at", "")))

    @staticmethod
    def _compact_result(
        tracking: dict[str, Any],
        *,
        created: bool,
        refreshed: bool,
    ) -> dict[str, Any]:
        intent = tracking.get("intent", {})
        summary = tracking.get("summary", {})
        recommendation = tracking.get("recommendation", {})
        history = tracking.get("history", [])
        return {
            "status": "success",
            "source": "smart_trip_tracker",
            "tracking_id": tracking.get("id"),
            "created": created,
            "refreshed": refreshed,
            "route": {
                "origin": intent.get("origin"),
                "destination": intent.get("destination"),
                "departure_date": intent.get("departure_date"),
                "return_date": intent.get("return_date"),
            },
            "prices": {
                "current": summary.get("current_price"),
                "minimum": summary.get("minimum_price"),
                "average": summary.get("average_price"),
                "difference_from_minimum": summary.get("difference_from_min"),
            },
            "recommendation": {
                "status": recommendation.get("status"),
                "message": recommendation.get("message"),
            },
            "history_points": len(history) if isinstance(history, list) else 0,
        }
