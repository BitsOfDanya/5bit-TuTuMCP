from uuid import uuid4

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    login: str = Field(index=True, unique=True, max_length=254)
    display_name: str = Field(max_length=80)
    password_hash: str | None = Field(default=None, max_length=512)
    created_at: int


class AuthChallenge(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    login: str = Field(index=True, max_length=254)
    code_digest: str = Field(max_length=64)
    expires_at: int
    requested_at: int
    attempts: int = 0
    consumed: bool = False
