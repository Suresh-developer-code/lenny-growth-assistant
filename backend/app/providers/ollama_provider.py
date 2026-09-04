"""Local LLM provider backed by Ollama (`/api/chat`, streaming NDJSON)."""
import json
from collections.abc import AsyncGenerator

import httpx
import structlog

from app.config import get_settings
from app.providers.base import BaseLLMProvider, ProviderUnavailableError

logger = structlog.get_logger(__name__)


class OllamaProvider(BaseLLMProvider):
    name = "ollama"

    def __init__(self, base_url: str | None = None, model: str | None = None):
        settings = get_settings()
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.ollama_model
        self.timeout = settings.ollama_timeout_seconds

    async def generate_response(
        self,
        messages: list[dict[str, str]],
        system_prompt: str,
        temperature: float = 0.3,
    ) -> AsyncGenerator[str, None]:
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system_prompt}, *messages],
            "stream": True,
            "options": {"temperature": temperature},
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as response:
                    if response.status_code != 200:
                        body = await response.aread()
                        logger.warning("ollama.non_200", status=response.status_code, body=body[:500])
                        raise ProviderUnavailableError(
                            f"Ollama returned HTTP {response.status_code}. "
                            f"Is the model '{self.model}' pulled? Try `ollama pull {self.model}`."
                        )
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        chunk = json.loads(line)
                        content = chunk.get("message", {}).get("content", "")
                        if content:
                            yield content
                        if chunk.get("done"):
                            break
        except httpx.ConnectError as exc:
            logger.warning("ollama.connect_error", base_url=self.base_url)
            raise ProviderUnavailableError(
                f"Could not reach Ollama at {self.base_url}. "
                "Start it with `ollama serve` and ensure the model is pulled."
            ) from exc
        except httpx.TimeoutException as exc:
            raise ProviderUnavailableError(
                f"Ollama did not respond within {self.timeout}s."
            ) from exc

    async def health_check(self) -> tuple[bool, str]:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                if resp.status_code == 200:
                    models = [m.get("name") for m in resp.json().get("models", [])]
                    if self.model not in models and models:
                        return True, f"reachable, but '{self.model}' not in pulled models: {models}"
                    return True, "reachable"
                return False, f"HTTP {resp.status_code}"
        except Exception as exc:  # noqa: BLE001 - health checks must never raise
            return False, str(exc)
