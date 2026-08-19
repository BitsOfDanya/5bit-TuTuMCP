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

    openai_api_key: SecretStr
    openai_model: str = "gpt-5.6-luna"
    agent_system_prompt: str = "You are a helpful assistant. Be concise and accurate."


@lru_cache
def get_settings() -> Settings:
    return Settings()
