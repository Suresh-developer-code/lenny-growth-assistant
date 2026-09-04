"""Unified LLM provider interface.

Any provider (local or cloud) implements this one async streaming method.
Nothing outside this package should know which concrete provider is active.
"""
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator


class ProviderUnavailableError(Exception):
    """Raised when the requested provider cannot serve a request right now
    (missing API key, connection refused, etc). The API layer turns this
    into a structured 503 — providers never silently fall back to a
    different provider on their own.
    """


class BaseLLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def generate_response(
        self,
        messages: list[dict[str, str]],
        system_prompt: str,
        temperature: float = 0.3,
    ) -> AsyncGenerator[str, None]:
        """Stream response tokens for the given conversation."""
        raise NotImplementedError
        yield ""  # pragma: no cover - keeps this an async generator for type checkers

    @abstractmethod
    async def health_check(self) -> tuple[bool, str]:
        """Return (ok, detail) without raising."""
        raise NotImplementedError
