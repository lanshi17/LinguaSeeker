"""Model server configuration — environment variables only.

This service is fully decoupled from the backend project. All configuration
comes from environment variables (set by docker-compose, systemd, or shell).
An optional ``.env`` file in the service directory is read for local dev.
No external config files are loaded.
"""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


# ── Settings model ──────────────────────────────────────────────────────────

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # Server
    host: str = "0.0.0.0"
    port: int = 8001
    log_level: str = "info"
    api_key: str = ""  # API key for Bearer auth; empty = disabled

    # HuggingFace cache
    hf_home: str = os.path.expanduser("~/.cache/huggingface/hub")

    # Embedding model
    embedding_model_id: str = "Qwen/Qwen3-Embedding-0.6B"
    embedding_dimension: int = 1024
    embedding_max_model_len: int = 8192

    # Rerank model
    rerank_model_id: str = "BAAI/bge-reranker-v2-m3"
    rerank_max_model_len: int = 8192

    # LLM model (placeholder — for future local LLM)
    llm_model_id: str = ""

    # Document parsing model (MinerU)
    doc_parse_model_id: str = ""
    doc_parse_image_analysis: bool = False
    doc_parse_backend: str = "vlm"
    doc_parse_model_path: str = ""

    # vllm shared settings
    vllm_gpu_memory_utilization: float = 0.9
    embedding_gpu_memory_utilization: float = 0.9
    rerank_gpu_memory_utilization: float = 0.9
    doc_parse_gpu_memory_utilization: float = 0.9


@lru_cache(maxsize=1)
def get_config() -> Settings:
    return Settings()
