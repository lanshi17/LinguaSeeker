"""Model server configuration — reads env vars / .env files."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env.local", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Server
    host: str = "0.0.0.0"
    port: int = 8001
    log_level: str = "info"

    # HuggingFace cache
    hf_home: str = "/home/yangzs/.cache/huggingface/hub"

    # Embedding model
    embedding_model_id: str = "Qwen/Qwen3-Embedding-0.6B"
    embedding_dimension: int = 1024

    # Rerank model
    rerank_model_id: str = "BAAI/bge-reranker-v2-m3"

    # LLM model (placeholder — for future local LLM)
    llm_model_id: str = ""


@lru_cache(maxsize=1)
def get_config() -> Settings:
    return Settings()
