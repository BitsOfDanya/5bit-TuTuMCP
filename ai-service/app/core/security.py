import secrets
from typing import Annotated

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


async def verify_internal_token(
    token: Annotated[str | None, Header(alias="X-AI-Service-Token")] = None,
) -> None:
    configured = get_settings().internal_api_token.get_secret_value()
    if configured and (token is None or not secrets.compare_digest(token, configured)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid AI service token.",
        )
