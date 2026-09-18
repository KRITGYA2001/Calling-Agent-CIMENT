from functools import lru_cache

import anthropic
from groq import Groq

from app.config import get_settings


@lru_cache
def _anthropic_client() -> anthropic.Anthropic:
    settings = get_settings()
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


@lru_cache
def _groq_client() -> Groq:
    settings = get_settings()
    return Groq(api_key=settings.groq_api_key)


def chat(messages: list[dict], system: str | None = None, max_tokens: int = 2048) -> str:
    """Note: Groq's gpt-oss models spend tokens on internal reasoning before
    the final answer, so keep max_tokens generous (a few hundred at least)."""
    """Provider-agnostic chat call. Switch providers via LLM_PROVIDER in .env."""
    settings = get_settings()
    system = system or "You are a helpful assistant."

    if settings.llm_provider == "groq":
        response = _groq_client().chat.completions.create(
            model=settings.groq_model,
            max_tokens=max_tokens,
            messages=[{"role": "system", "content": system}, *messages],
        )
        return response.choices[0].message.content or ""

    response = _anthropic_client().messages.create(
        model=settings.anthropic_model,
        max_tokens=max_tokens,
        system=system,
        messages=messages,
    )
    return "".join(block.text for block in response.content if block.type == "text")
