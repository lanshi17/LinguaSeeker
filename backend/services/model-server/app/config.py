"""Model server configuration — reads env vars / .env files."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_SERVICE_ROOT = Path(__file__).resolve().parents[1]
_BACKEND_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(
            _BACKEND_ROOT / ".env",
            _BACKEND_ROOT / ".env.local",
            _SERVICE_ROOT / ".env",
            _SERVICE_ROOT / ".env.local",
        ),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Server
    host: str = "0.0.0.0"
    port: int = 8001
    log_level: str = "info"

    # HuggingFace cache
    hf_home: str = os.path.expanduser("~/.cache/huggingface/hub")

    # Embedding model
    embedding_model_id: str = "Qwen/Qwen3-Embedding-0.6B"
    embedding_dimension: int = 1024

    # Rerank model
    rerank_model_id: str = "BAAI/bge-reranker-v2-m3"

    # LLM model (placeholder — for future local LLM)
    llm_model_id: str = ""

    # VLM model (MinerU)
    vlm_model_id: str = ""
    vlm_image_analysis: bool = False

    # vllm shared settings
    vllm_gpu_memory_utilization: float = 0.9


@lru_cache(maxsize=1)
def get_config() -> Settings:
    return Settings()
