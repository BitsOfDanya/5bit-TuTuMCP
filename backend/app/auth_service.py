import hashlib
import hmac
import secrets
import time
from typing import Any

import jwt
from pwdlib import PasswordHash
from sqlmodel import Session, select

from app.config import Settings
from app.models import AuthChallenge, User
from app.schemas import UserResponse

PASSWORD_HASHER = PasswordHash.recommended()
MAX_CODE_ATTEMPTS = 5
CODE_REQUEST_COOLDOWN_SECONDS = 30


class AuthError(Exception):
    pass


class AuthRateLimitError(AuthError):
    pass


class InvalidCodeError(AuthError):
    pass


class InvalidCredentialsError(AuthError):
    pass


def create_code_challenge(
    session: Session,
    login: str,
    settings: Settings,
) -> tuple[AuthChallenge, str]:
    now = int(time.time())
    recent = session.exec(
        select(AuthChallenge)
        .where(
            AuthChallenge.login == login,
            AuthChallenge.requested_at > now - CODE_REQUEST_COOLDOWN_SECONDS,
        )
        .order_by(AuthChallenge.requested_at.desc())
    ).first()
    if recent is not None:
        raise AuthRateLimitError("Подождите немного перед повторной отправкой кода.")

    code = f"{secrets.randbelow(1_000_000):06d}"
    challenge = AuthChallenge(
        login=login,
        code_digest=_code_digest(code, settings),
        expires_at=now + settings.auth_code_ttl_seconds,
        requested_at=now,
    )
    session.add(challenge)
    session.commit()
    session.refresh(challenge)
    return challenge, code


def verify_code(
    session: Session,
    challenge_id: str,
    code: str,
    settings: Settings,
) -> User:
    challenge = session.get(AuthChallenge, challenge_id)
    now = int(time.time())

    if (
        challenge is None
        or challenge.consumed
        or challenge.expires_at < now
        or challenge.attempts >= MAX_CODE_ATTEMPTS
    ):
        raise InvalidCodeError("Код недействителен или истёк. Запросите новый.")

    challenge.attempts += 1
    if not hmac.compare_digest(challenge.code_digest, _code_digest(code, settings)):
        session.add(challenge)
        session.commit()
        raise InvalidCodeError("Неверный код. Проверьте цифры и попробуйте ещё раз.")

    challenge.consumed = True
    user = _get_or_create_user(session, challenge.login)
    session.add(challenge)
    session.commit()
    session.refresh(user)
    return user


def authenticate_with_password(
    session: Session,
    email: str,
    password: str,
) -> User:
    user = session.exec(select(User).where(User.login == email)).first()

    if user is None:
        user = User(
            login=email,
            display_name=_display_name(email),
            password_hash=PASSWORD_HASHER.hash(password),
            created_at=int(time.time()),
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user

    if user.password_hash is None:
        raise InvalidCredentialsError("Неверная почта или пароль.")

    is_valid, updated_hash = PASSWORD_HASHER.verify_and_update(password, user.password_hash)
    if not is_valid:
        raise InvalidCredentialsError("Неверная почта или пароль.")
    if updated_hash is not None:
        user.password_hash = updated_hash
        session.add(user)
        session.commit()
        session.refresh(user)

    return user


def create_session_token(user: User, settings: Settings) -> str:
    now = int(time.time())
    payload = {
        "sub": user.id,
        "iat": now,
        "exp": now + settings.auth_session_ttl_seconds,
        "type": "session",
    }
    return jwt.encode(
        payload,
        settings.auth_secret_key.get_secret_value(),
        algorithm="HS256",
    )


def user_from_token(
    session: Session,
    token: str | None,
    settings: Settings,
) -> User | None:
    if not token:
        return None

    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.auth_secret_key.get_secret_value(),
            algorithms=["HS256"],
        )
    except jwt.PyJWTError:
        return None

    if payload.get("type") != "session":
        return None
    user_id = payload.get("sub")
    return session.get(User, user_id) if isinstance(user_id, str) else None


def user_response(user: User) -> UserResponse:
    return UserResponse(id=user.id, login=user.login, display_name=user.display_name)


def _get_or_create_user(session: Session, login: str) -> User:
    user = session.exec(select(User).where(User.login == login)).first()
    if user is not None:
        return user

    user = User(
        login=login,
        display_name=_display_name(login),
        created_at=int(time.time()),
    )
    session.add(user)
    session.flush()
    return user


def _display_name(login: str) -> str:
    if "@" in login:
        name = login.split("@", maxsplit=1)[0].replace(".", " ").replace("_", " ")
        return name[:80].title() or "Путешественник"
    return f"Путешественник {login[-4:]}"


def _code_digest(code: str, settings: Settings) -> str:
    return hmac.new(
        settings.auth_secret_key.get_secret_value().encode(),
        code.encode(),
        hashlib.sha256,
    ).hexdigest()
