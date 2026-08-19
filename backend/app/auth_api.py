from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.auth_service import (
    AuthRateLimitError,
    InvalidCodeError,
    InvalidCredentialsError,
    authenticate_with_password,
    create_code_challenge,
    create_session_token,
    user_from_token,
    user_response,
    verify_code,
)
from app.config import Settings, get_settings
from app.db import SessionDep
from app.schemas import (
    AuthCodeRequest,
    AuthCodeRequested,
    AuthCodeVerifyRequest,
    AuthSessionResponse,
    MessageResponse,
    PasswordAuthRequest,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
SettingsDep = Annotated[Settings, Depends(get_settings)]


@router.post("/code/request")
def request_auth_code(
    payload: AuthCodeRequest,
    session: SessionDep,
    settings: SettingsDep,
) -> AuthCodeRequested:
    try:
        challenge, code = create_code_challenge(session, payload.login, settings)
    except AuthRateLimitError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    return AuthCodeRequested(
        challenge_id=challenge.id,
        expires_in=settings.auth_code_ttl_seconds,
        debug_code=code if settings.auth_debug else None,
    )


@router.post("/code/verify")
def verify_auth_code(
    payload: AuthCodeVerifyRequest,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
) -> AuthSessionResponse:
    try:
        user = verify_code(session, payload.challenge_id, payload.code, settings)
    except InvalidCodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    _set_session_cookie(response, create_session_token(user, settings), settings)
    return AuthSessionResponse(user=user_response(user))


@router.post("/password")
def password_auth(
    payload: PasswordAuthRequest,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
) -> AuthSessionResponse:
    try:
        user = authenticate_with_password(session, payload.email, payload.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    _set_session_cookie(response, create_session_token(user, settings), settings)
    return AuthSessionResponse(user=user_response(user))


@router.get("/me")
def read_session(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
) -> AuthSessionResponse:
    user = user_from_token(session, request.cookies.get(settings.auth_cookie_name), settings)
    return AuthSessionResponse(user=user_response(user) if user is not None else None)


@router.post("/logout")
def logout(response: Response, settings: SettingsDep) -> MessageResponse:
    response.delete_cookie(
        key=settings.auth_cookie_name,
        path="/",
        httponly=True,
        samesite="lax",
        secure=not settings.auth_debug,
    )
    return MessageResponse(message="Вы вышли из аккаунта.")


def _set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        max_age=settings.auth_session_ttl_seconds,
        path="/",
        httponly=True,
        samesite="lax",
        secure=not settings.auth_debug,
    )
