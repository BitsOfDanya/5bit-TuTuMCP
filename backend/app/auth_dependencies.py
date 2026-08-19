from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from app.auth_service import user_from_token
from app.config import Settings, get_settings
from app.db import SessionDep
from app.models import User


def get_current_user(
    request: Request,
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    user = user_from_token(
        session,
        request.cookies.get(settings.auth_cookie_name),
        settings,
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Войдите в аккаунт, чтобы настроить предпочтения.",
        )
    return user


def get_optional_current_user(
    request: Request,
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
) -> User | None:
    return user_from_token(
        session,
        request.cookies.get(settings.auth_cookie_name),
        settings,
    )


CurrentUserDep = Annotated[User, Depends(get_current_user)]
OptionalCurrentUserDep = Annotated[User | None, Depends(get_optional_current_user)]
