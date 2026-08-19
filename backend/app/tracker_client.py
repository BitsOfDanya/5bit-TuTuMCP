from functools import lru_cache
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import Depends
from pydantic import ValidationError

from app.config import get_settings
from app.schemas import TrackingPayload, TripTrackingResponse


class SmartTripTrackerError(RuntimeError):
    def __init__(self, detail: str, status_code: int = 502) -> None:
        super().__init__(detail)
        self.status_code = status_code


class SmartTripTrackerClient:
    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    async def create(self, payload: TrackingPayload) -> TripTrackingResponse:
        return await self._request(
            "POST",
            "/api/v1/trips",
            json=payload.model_dump(mode="json"),
        )

    async def get(self, tracking_id: UUID) -> TripTrackingResponse:
        return await self._request("GET", f"/api/v1/trips/{tracking_id}")

    async def refresh(self, tracking_id: UUID) -> TripTrackingResponse:
        return await self._request("POST", f"/api/v1/trips/{tracking_id}/refresh")

    async def stop(self, tracking_id: UUID) -> TripTrackingResponse:
        return await self._request("DELETE", f"/api/v1/trips/{tracking_id}")

    async def _request(self, method: str, path: str, **kwargs: object) -> TripTrackingResponse:
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
            ) as client:
                response = await client.request(method, path, **kwargs)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code < 400 or status_code >= 500:
                status_code = 502
            raise SmartTripTrackerError(
                _response_detail(exc.response),
                status_code,
            ) from exc
        except httpx.HTTPError as exc:
            raise SmartTripTrackerError("Сервис отслеживания цен недоступен.") from exc

        try:
            return TripTrackingResponse.model_validate(response.json())
        except (ValueError, ValidationError) as exc:
            raise SmartTripTrackerError(
                "Сервис отслеживания цен вернул некорректный ответ."
            ) from exc


def _response_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return "Не удалось выполнить запрос к сервису отслеживания цен."
    detail = payload.get("detail") if isinstance(payload, dict) else None
    return detail if isinstance(detail, str) else "Не удалось выполнить запрос."


@lru_cache
def get_smart_trip_tracker_client() -> SmartTripTrackerClient:
    settings = get_settings()
    return SmartTripTrackerClient(
        settings.smart_trip_tracker_url,
        settings.smart_trip_tracker_timeout_seconds,
    )


SmartTripTrackerClientDep = Annotated[
    SmartTripTrackerClient,
    Depends(get_smart_trip_tracker_client),
]
