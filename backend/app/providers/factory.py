"""Resolves which LLM provider serves a given request.

Precedence: explicit request field > DEFAULT_LLM_PROVIDER env var > 'ollama'.
Never silently substitutes one provider for another on failure — see
docs/architecture.md §5 for the rationale.
"""
from app.config import get_settings
from app.providers.base import BaseLLMProvider
from app.providers.cloud_provider import AnthropicProvider
from app.providers.ollama_provider import OllamaProvider


def get_provider(requested: str | None = None) -> BaseLLMProvider:
    settings = get_settings()
    provider_name = requested or settings.default_llm_provider

    if provider_name == "ollama":
        return OllamaProvider()
    if provider_name == "anthropic":
        return AnthropicProvider()

    raise ValueError(f"Unknown provider: {provider_name}")


async def check_all_providers() -> dict[str, tuple[bool, str]]:
    """Used by /api/health — checks providers without raising."""
    settings = get_settings()
    results: dict[str, tuple[bool, str]] = {}

    ollama = OllamaProvider()
    results["ollama"] = await ollama.health_check()

    if settings.anthropic_api_key:
        try:
            anthropic = AnthropicProvider()
            results["anthropic"] = await anthropic.health_check()
        except Exception as exc:  # noqa: BLE001
            results["anthropic"] = (False, str(exc))
    else:
        results["anthropic"] = (False, "no API key configured (optional)")

    return results
