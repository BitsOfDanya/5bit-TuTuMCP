import re

from pydantic import BaseModel, Field, field_validator

EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class HealthResponse(BaseModel):
    status: str


class AgentRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20_000)


class AgentResponse(BaseModel):
    response: str


class AuthCodeRequest(BaseModel):
    login: str = Field(min_length=5, max_length=254)

    @field_validator("login")
    @classmethod
    def normalize_login(cls, value: str) -> str:
        return normalize_login(value)


class AuthCodeRequested(BaseModel):
    challenge_id: str
    expires_in: int
    debug_code: str | None = None


class AuthCodeVerifyRequest(BaseModel):
    challenge_id: str = Field(min_length=16, max_length=128)
    code: str = Field(pattern=r"^\d{6}$")


class PasswordAuthRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not EMAIL_PATTERN.fullmatch(normalized):
            raise ValueError("Enter a valid email address")
        return normalized


class UserResponse(BaseModel):
    id: str
    login: str
    display_name: str


class AuthSessionResponse(BaseModel):
    user: UserResponse | None


class MessageResponse(BaseModel):
    message: str


def normalize_login(value: str) -> str:
    normalized = value.strip().lower()
    if "@" in normalized:
        if not EMAIL_PATTERN.fullmatch(normalized):
            raise ValueError("Enter a valid email address")
        return normalized

    digits = re.sub(r"\D", "", normalized)
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    if not 10 <= len(digits) <= 15:
        raise ValueError("Enter a valid phone number or email")
    return "+" + digits
