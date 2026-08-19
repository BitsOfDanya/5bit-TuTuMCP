from functools import lru_cache
from typing import Annotated, Any

import httpx
from fastapi import Depends

from app.config import get_settings


class TripRescueError(RuntimeError):
    def __init__(self, detail: str, status_code: int = 502) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class TripRescueClient:
    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    async def get_cold_start_questions(self, *, limit: int = 4) -> dict[str, Any]:
        return await self._request_json(
            "GET",
            "/api/v1/preferences/cold-start/questions",
            params={"limit": limit},
        )

    async def complete_cold_start(
        self,
        *,
        profile_id: str,
        choices: list[dict[str, str]],
        replace: bool,
    ) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            "/api/v1/preferences/cold-start/complete",
            json={
                "profile_id": profile_id,
                "choices": choices,
                "replace": replace,
            },
        )

    async def get_profile(self, profile_id: str) -> dict[str, Any] | None:
        try:
            return await self._request_json("GET", f"/api/v1/preferences/{profile_id}")
        except TripRescueError as exc:
            if exc.status_code == 404:
                return None
            raise

    async def health(self) -> dict[str, Any]:
        return await self._request_json("GET", "/health")

    async def rescue_from_text(
        self,
        *,
        trip: dict[str, object],
        journey: dict[str, object],
        message: str,
        profile_id: str,
    ) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            "/api/v1/rescue/from-text/public",
            json={
                "current_trip": trip,
                "current_journey": journey,
                "message": message,
                "preference_profile_id": profile_id,
            },
        )

    async def what_if_from_text(
        self,
        *,
        trip: dict[str, object],
        journey: dict[str, object],
        message: str,
        profile_id: str,
    ) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            "/api/v1/what-if/from-text/public",
            json={
                "current_trip": trip,
                "current_journey": journey,
                "message": message,
                "preference_profile_id": profile_id,
            },
        )

    async def build_group_profile(
        self,
        *,
        group_id: str,
        profile_ids: list[str],
    ) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            "/api/v1/preferences/group/profile",
            json={"group_id": group_id, "profile_ids": profile_ids},
        )

    async def rerank_group(
        self,
        *,
        group_id: str,
        profile_ids: list[str],
        candidates: list[dict[str, object]],
    ) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            "/api/v1/preferences/group/rerank",
            json={
                "group_id": group_id,
                "profile_ids": profile_ids,
                "candidates": candidates,
            },
        )

    async def record_preference_feedback(
        self,
        *,
        profile_id: str,
        candidate: dict[str, object],
        action: str = "choose",
    ) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            "/api/v1/preferences/feedback",
            json={
                "profile_id": profile_id,
                "action": action,
                "candidate": candidate,
                "shown_candidates": [],
            },
        )

    async def _request_json(self, method: str, path: str, **kwargs: object) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
            ) as client:
                response = await client.request(method, path, **kwargs)
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise TripRescueError(
                _response_detail(exc.response),
                exc.response.status_code,
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise TripRescueError("Decision Intelligence service is unavailable.") from exc

        if not isinstance(payload, dict):
            raise TripRescueError("Decision Intelligence returned an invalid response.")
        return payload


def _response_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return "Decision Intelligence request failed."
    detail = payload.get("detail") if isinstance(payload, dict) else None
    if isinstance(detail, str):
        return detail
    if isinstance(detail, dict) and isinstance(detail.get("message"), str):
        return detail["message"]
    return "Decision Intelligence request failed."


@lru_cache
def get_trip_rescue_client() -> TripRescueClient:
    settings = get_settings()
    return TripRescueClient(
        settings.trip_rescue_url,
        settings.trip_rescue_timeout_seconds,
    )


TripRescueClientDep = Annotated[TripRescueClient, Depends(get_trip_rescue_client)]
