"""Embedding function abstraction.

Default: sentence-transformers/all-MiniLM-L6-v2, running locally, no network
call and no API key needed — keeps the whole retrieval path usable offline.
Alternative: Ollama's nomic-embed-text, if EMBEDDING_PROVIDER=ollama.
"""
from functools import lru_cache

import httpx

from app.config import get_settings


@lru_cache
def _get_st_model():
    """Lazily import & cache the sentence-transformers model (heavy import)."""
    from sentence_transformers import SentenceTransformer

    settings = get_settings()
    return SentenceTransformer(settings.embedding_model)


async def embed_text(text: str) -> list[float]:
    """Return a single embedding vector for `text`."""
    settings = get_settings()

    if settings.embedding_provider == "ollama":
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.ollama_base_url}/api/embeddings",
                json={"model": "nomic-embed-text", "prompt": text},
            )
            resp.raise_for_status()
            return resp.json()["embedding"]

    # sentence-transformers path (default) — CPU inference, no network needed.
    model = _get_st_model()
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()


async def embed_batch(texts: list[str]) -> list[list[float]]:
    settings = get_settings()
    if settings.embedding_provider == "ollama":
        return [await embed_text(t) for t in texts]

    model = _get_st_model()
    vectors = model.encode(texts, normalize_embeddings=True, batch_size=32, show_progress_bar=False)
    return [v.tolist() for v in vectors]
