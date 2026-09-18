from functools import lru_cache

import anthropic

from app.config import get_settings


@lru_cache
def get_client() -> anthropic.Anthropic:
    settings = get_settings()
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def chat(messages: list[dict], system: str | None = None, max_tokens: int = 1024) -> str:
    settings = get_settings()
    client = get_client()
    response = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=max_tokens,
        system=system or "You are a helpful assistant.",
        messages=messages,
    )
    return "".join(block.text for block in response.content if block.type == "text")
