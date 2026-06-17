"""Model server configuration — reads layered YAML config and env vars."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from acmg_config_loader import load_backend_config_into_env
from pydantic_settings import BaseSettings, SettingsConfigDict


# File is at services/model-server/app/config.py.
# parents[0] = app, parents[1] = model-server, parents[2] = services,
# parents[3] = repo root. The backend root we need to load `config/` from is
# `repo_root/backend/`.
_BACKEND_ROOT = Path(__file__).resolve().parents[3] / "backend"

load_backend_config_into_env(_BACKEND_ROOT)


# ── Settings model ──────────────────────────────────────────────────────

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore",
    )

    # Server
    host: str = "127.0.0.1"
    port: int = 8001
    log_level: str = "info"
    api_key: str = ""  # API key for Bearer auth; empty = disabled

    # HuggingFace cache
    hf_home: str = os.path.expanduser("~/.cache/huggingface/hub")

    # Embedding model
    embedding_model_id: str = "Qwen/Qwen3-Embedding-0.6B"
    embedding_dimension: int = 1024
    embedding_max_model_len: int = 32768

    # Rerank model
    rerank_model_id: str = "BAAI/bge-reranker-v2-m3"

    # LLM model (placeholder — for future local LLM)
    llm_model_id: str = ""

    # Document parsing model (MinerU)
    doc_parse_model_id: str = ""
    doc_parse_image_analysis: bool = False

    # vllm shared settings
    vllm_gpu_memory_utilization: float = 0.9
    embedding_gpu_memory_utilization: float = 0.9
    rerank_gpu_memory_utilization: float = 0.9
    doc_parse_gpu_memory_utilization: float = 0.9


@lru_cache(maxsize=1)
def get_config() -> Settings:
    return Settings()
