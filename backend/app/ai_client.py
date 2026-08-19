from functools import lru_cache
from typing import Annotated, Literal

import httpx
from fastapi import Depends
from pydantic import BaseModel, Field

from app.config import get_settings
from app.document_uploads import DocumentMediaType
from app.schemas import (
    AgentNextAction,
    PassengerDocumentData,
    SearchOption,
    TravelPlan,
    TripDetails,
)


class AIChatResult(BaseModel):
    response: str
    trip: TripDetails
    missing_fields: list[str]
    is_complete: bool
    next_action: AgentNextAction
    plan: TravelPlan
    tools_used: list[str]
    tool_statuses: dict[str, str]
    search_options: list[SearchOption] = Field(default_factory=list)
    redirect_url: str | None = None


class AIDocumentResult(BaseModel):
    media_type: Literal["image/png", "image/jpeg", "application/pdf"]
    document: PassengerDocumentData
    missing_fields: list[str]
    manual_review_required: bool


class AIServiceError(RuntimeError):
    pass


class AIServiceClient:
    def __init__(self, base_url: str, token: str, timeout_seconds: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout_seconds

    @property
    def _headers(self) -> dict[str, str]:
        return {"X-AI-Service-Token": self._token} if self._token else {}

    async def chat(
        self,
        *,
        messages: list[dict[str, str]],
        current_trip: TripDetails,
    ) -> AIChatResult:
        response = await self._request(
            "POST",
            "/api/v1/ai/chat",
            json={
                "messages": messages,
                "current_trip": current_trip.model_dump(mode="json"),
            },
        )
        return AIChatResult.model_validate(response.json())

    async def health(self) -> dict[str, str]:
        response = await self._request("GET", "/health")
        try:
            payload = response.json()
        except ValueError as exc:
            raise AIServiceError("AI service returned an invalid health response.") from exc
        if not isinstance(payload, dict) or payload.get("status") != "ok":
            raise AIServiceError("AI service is not healthy.")
        return {"status": "ok", "service": str(payload.get("service", "ai-service"))}

    async def extract_document(
        self,
        *,
        filename: str,
        media_type: DocumentMediaType,
        content: bytes,
    ) -> AIDocumentResult:
        response = await self._request(
            "POST",
            "/api/v1/ai/documents/extract",
            files={"document": (filename, content, media_type)},
        )
        return AIDocumentResult.model_validate(response.json())

    async def _request(self, method: str, path: str, **kwargs: object) -> httpx.Response:
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                headers=self._headers,
                timeout=self._timeout,
            ) as client:
                response = await client.request(method, path, **kwargs)
                response.raise_for_status()
                return response
        except httpx.HTTPStatusError as exc:
            detail = _response_detail(exc.response)
            raise AIServiceError(detail) from exc
        except httpx.HTTPError as exc:
            raise AIServiceError("AI service is unavailable.") from exc


def _response_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return "AI service request failed."
    detail = payload.get("detail") if isinstance(payload, dict) else None
    return detail if isinstance(detail, str) else "AI service request failed."


@lru_cache
def get_ai_service_client() -> AIServiceClient:
    settings = get_settings()
    return AIServiceClient(
        settings.ai_service_url,
        settings.ai_service_token.get_secret_value(),
        settings.ai_service_timeout_seconds,
    )


AIServiceClientDep = Annotated[AIServiceClient, Depends(get_ai_service_client)]
