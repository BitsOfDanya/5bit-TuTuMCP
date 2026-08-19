from functools import lru_cache
from typing import Any

import httpx


class SmartTripTrackerUnavailable(RuntimeError):
    pass


class SmartTripTrackerClient:
    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    async def list(self) -> list[dict[str, Any]]:
        payload = await self._request("GET", "/api/v1/trips")
        items = payload.get("items")
        return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []

    async def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/api/v1/trips", json=payload)

    async def refresh(self, tracking_id: str) -> dict[str, Any]:
        return await self._request("POST", f"/api/v1/trips/{tracking_id}/refresh")

    async def health(self) -> dict[str, str]:
        payload = await self._request("GET", "/health")
        if payload.get("status") != "ok":
            raise SmartTripTrackerUnavailable("Smart Trip Tracker is not healthy.")
        return {"status": "ok", "service": "smart-trip-tracker"}

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
            ) as client:
                response = await client.request(method, path, **kwargs)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise SmartTripTrackerUnavailable(
                "Smart Trip Tracker is unavailable."
            ) from exc
        if not isinstance(payload, dict):
            raise SmartTripTrackerUnavailable(
                "Smart Trip Tracker returned an unexpected payload."
            )
        return payload


@lru_cache
def get_smart_trip_tracker_client() -> SmartTripTrackerClient:
    from app.core.config import get_settings

    settings = get_settings()
    return SmartTripTrackerClient(
        settings.smart_trip_tracker_url,
        settings.smart_trip_tracker_timeout_seconds,
    )
