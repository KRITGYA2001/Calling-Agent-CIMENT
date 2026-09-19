from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    llm_provider: str = "groq"  # "groq" (free) or "anthropic" (paid, higher quality)

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"

    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"

    # "*" is fine here: no cookies/auth are used, and this only guards the demo API.
    cors_origins: list[str] = ["*"]

    # Vapi (voice AI platform) — console.vapi.ai
    vapi_api_key: str = ""  # private/server key, used to create assistants & verify webhooks
    vapi_public_key: str = ""  # public key, safe to ship to the frontend for web calls
    vapi_webhook_secret: str = ""  # optional: set a server-message secret in Vapi to verify webhook calls

    vapi_assistant_id: str = ""  # the assistant created by scripts/create_assistant.py
    vapi_phone_number_id: str = ""  # Vapi phone number (the imported Vobiz number) used for outbound dialling
    human_handoff_number: str = ""  # E.164 number of the human agent for warm transfers (optional)
    human_agent_name: str = "Aarav"
    enforce_calling_hours: bool = False  # ACMA hours check; off by default so the demo can run any time

    # Journey completion sandbox — filled in once the hackathon reveals the real endpoint
    journey_sandbox_url: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
