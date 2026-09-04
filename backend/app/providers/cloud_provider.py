"""Cloud LLM provider(s). Anthropic Claude is implemented; OpenAI would follow
the identical pattern and register in factory.py.
"""
from collections.abc import AsyncGenerator

import structlog

from app.config import get_settings
from app.providers.base import BaseLLMProvider, ProviderUnavailableError

logger = structlog.get_logger(__name__)


class AnthropicProvider(BaseLLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        settings = get_settings()
        self.api_key = api_key or settings.anthropic_api_key
        self.model = model or settings.anthropic_model

        if not self.api_key:
            # Fail fast and clearly rather than lazily erroring mid-stream.
            raise ProviderUnavailableError(
                "ANTHROPIC_API_KEY is not set. Add it to .env, or select the "
                "local Ollama provider instead."
            )

        # Imported lazily so the SDK is only required when this provider is used.
        from anthropic import AsyncAnthropic

        self._client = AsyncAnthropic(api_key=self.api_key)

    async def generate_response(
        self,
        messages: list[dict[str, str]],
        system_prompt: str,
        temperature: float = 0.3,
    ) -> AsyncGenerator[str, None]:
        try:
            async with self._client.messages.stream(
                model=self.model,
                max_tokens=4096,
                temperature=temperature,
                system=system_prompt,
                messages=messages,
            ) as stream:
                async for text in stream.text_stream:
                    yield text
        except Exception as exc:  # noqa: BLE001
            logger.warning("anthropic.stream_error", error=str(exc))
            raise ProviderUnavailableError(f"Anthropic API error: {exc}") from exc

    async def health_check(self) -> tuple[bool, str]:
        if not self.api_key:
            return False, "no API key configured"
        return True, "key configured (not making a billed call for health check)"
