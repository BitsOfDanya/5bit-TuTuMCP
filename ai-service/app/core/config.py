from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_DIR = Path(__file__).resolve().parents[2]
ROOT_ENV = APP_DIR.parent / ".env"
LEGACY_BACKEND_ENV = APP_DIR.parent / "backend" / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # The backend file is a compatibility fallback while local secrets are moved.
        env_file=(ROOT_ENV, LEGACY_BACKEND_ENV, APP_DIR / ".env"),
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    app_host: str = "0.0.0.0"
    app_port: int = 8020
    openai_api_key: SecretStr = SecretStr("")
    openai_model: str = "gpt-5.6-luna"
    openai_reasoning_effort: str = "none"
    document_extraction_model: str = "gpt-5.6-luna"
    agent_system_prompt: str = "Be concise, friendly, and accurate."
    max_document_size_bytes: int = 10 * 1024 * 1024
    constraint_negotiator_url: str = "http://127.0.0.1:8010"
    constraint_negotiator_timeout_seconds: float = 45.0
    smart_trip_tracker_url: str = "http://127.0.0.1:8001"
    smart_trip_tracker_timeout_seconds: float = 60.0
    internal_api_token: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices("INTERNAL_API_TOKEN", "AI_SERVICE_TOKEN"),
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
