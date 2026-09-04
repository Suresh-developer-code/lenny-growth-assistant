"""Centralized, env-driven configuration.

Every setting an evaluator might need to change lives here and is documented
in .env.example. Nothing in the application code should read os.environ
directly outside of this module.
"""
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- App ---
    app_name: str = "Lenny Growth Assistant"
    environment: Literal["local", "staging", "production"] = "local"
    log_level: str = "INFO"

    # --- Database ---
    database_url: str = (
        "postgresql+asyncpg://postgres:password123@localhost:5432/lenny_assistant"
    )

    # --- Model routing ---
    default_llm_provider: Literal["ollama", "anthropic"] = "ollama"

    # --- Ollama (local, required for the demo) ---
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"
    ollama_timeout_seconds: float = 60.0

    # --- Anthropic (cloud, optional) ---
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-5"

    # --- Embeddings ---
    embedding_provider: Literal["sentence_transformers", "ollama"] = "sentence_transformers"
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384

    # --- Retrieval ---
    retrieval_top_k: int = 5
    retrieval_similarity_threshold: float = 0.65

    # --- Ingestion ---
    transcript_source_url: str | None = None
    chunk_target_tokens: int = 650
    chunk_overlap_tokens: int = 100

    # --- CORS ---
    cors_allow_origins: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
