"""Unit tests for the provider factory and provider-level error handling.

Verifies the "explicit failure, not implicit substitution" contract from
architecture.md §5: a missing Anthropic key must raise, never silently
route to Ollama, and an unknown provider name must raise ValueError.
"""
import pytest

from app.config import get_settings
from app.providers.base import ProviderUnavailableError
from app.providers.cloud_provider import AnthropicProvider
from app.providers.factory import get_provider
from app.providers.ollama_provider import OllamaProvider


def test_factory_defaults_to_configured_default_provider(monkeypatch):
    monkeypatch.setenv("DEFAULT_LLM_PROVIDER", "ollama")
    get_settings.cache_clear()
    provider = get_provider(None)
    assert isinstance(provider, OllamaProvider)
    get_settings.cache_clear()


def test_factory_explicit_request_overrides_default(monkeypatch):
    monkeypatch.setenv("DEFAULT_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-123")
    get_settings.cache_clear()
    provider = get_provider("anthropic")
    assert isinstance(provider, AnthropicProvider)
    get_settings.cache_clear()


def test_factory_unknown_provider_raises_value_error():
    with pytest.raises(ValueError):
        get_provider("not-a-real-provider")


def test_anthropic_provider_without_key_raises_provider_unavailable(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    get_settings.cache_clear()
    with pytest.raises(ProviderUnavailableError):
        AnthropicProvider(api_key=None)
    get_settings.cache_clear()


def test_anthropic_provider_never_falls_back_silently(monkeypatch):
    """Even though Ollama is the configured default, requesting the cloud
    provider explicitly with no key must fail loudly rather than quietly
    returning an OllamaProvider instance instead.
    """
    monkeypatch.setenv("DEFAULT_LLM_PROVIDER", "ollama")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    get_settings.cache_clear()
    with pytest.raises(ProviderUnavailableError):
        get_provider("anthropic")
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_ollama_health_check_reports_failure_without_raising():
    provider = OllamaProvider(base_url="http://localhost:1")  # nothing listening
    ok, detail = await provider.health_check()
    assert ok is False
    assert isinstance(detail, str)
