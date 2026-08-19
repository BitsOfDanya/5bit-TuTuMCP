from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: SecretStr = SecretStr("")
    openai_model: str = "gpt-5.6-luna"
    agent_system_prompt: str = "You are a helpful assistant. Be concise and accurate."
    database_url: str = "sqlite:///./.data/tutumcp.db"
    auth_secret_key: SecretStr = SecretStr("local-development-key-change-me-please")
    auth_cookie_name: str = "tutumcp_session"
    auth_debug: bool = True
    auth_code_ttl_seconds: int = 300
    auth_session_ttl_seconds: int = 60 * 60 * 24 * 7


@lru_cache
def get_settings() -> Settings:
    return Settings()
