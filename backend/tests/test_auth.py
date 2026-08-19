from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.db import get_session
from app.main import app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def override_session() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_session, None)


def test_passwordless_login_creates_session(client: TestClient) -> None:
    requested = client.post("/api/v1/auth/code/request", json={"login": "demo@example.com"})

    assert requested.status_code == 200
    payload = requested.json()
    assert payload["debug_code"]

    verified = client.post(
        "/api/v1/auth/code/verify",
        json={
            "challenge_id": payload["challenge_id"],
            "code": payload["debug_code"],
        },
    )

    assert verified.status_code == 200
    assert verified.json()["user"]["login"] == "demo@example.com"
    assert "tutumcp_session" in verified.cookies

    session = client.get("/api/v1/auth/me")
    assert session.status_code == 200
    assert session.json()["user"]["login"] == "demo@example.com"


def test_registration_creates_session_and_password_login_reuses_account(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Анна Петрова",
            "email": "traveller@example.com",
            "password": "very-safe-password",
        },
    )
    assert created.status_code == 201
    assert created.json()["user"]["display_name"] == "Анна Петрова"
    assert "tutumcp_session" in created.cookies

    client.post("/api/v1/auth/logout")
    signed_in = client.post(
        "/api/v1/auth/password",
        json={"email": "traveller@example.com", "password": "very-safe-password"},
    )
    assert signed_in.status_code == 200
    assert signed_in.json()["user"]["display_name"] == "Анна Петрова"


def test_registration_rejects_duplicate_email(client: TestClient) -> None:
    payload = {
        "name": "Анна",
        "email": "traveller@example.com",
        "password": "very-safe-password",
    }
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201

    duplicate = client.post("/api/v1/auth/register", json=payload)

    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "Аккаунт с такой почтой уже существует."


def test_password_auth_rejects_wrong_password(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={
            "name": "Анна",
            "email": "traveller@example.com",
            "password": "very-safe-password",
        },
    )
    response = client.post(
        "/api/v1/auth/password",
        json={"email": "traveller@example.com", "password": "not-the-password"},
    )

    assert response.status_code == 401


def test_password_auth_does_not_create_unknown_account(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/password",
        json={"email": "unknown@example.com", "password": "very-safe-password"},
    )

    assert response.status_code == 401
    assert client.get("/api/v1/auth/me").json()["user"] is None


def test_code_login_rejects_invalid_code(client: TestClient) -> None:
    requested = client.post("/api/v1/auth/code/request", json={"login": "+79991234567"})
    response = client.post(
        "/api/v1/auth/code/verify",
        json={
            "challenge_id": requested.json()["challenge_id"],
            "code": "000000",
        },
    )

    assert response.status_code == 400
