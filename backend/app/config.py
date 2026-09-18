from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    llm_provider: str = "groq"  # "groq" (free) or "anthropic" (paid, higher quality)

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"

    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"

    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
