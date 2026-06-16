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

# Load backend config first (shared API keys, LLM endpoints, etc.)
load_backend_config_into_env(_BACKEND_ROOT)

# Then load model-server's own config (model IDs, GPU settings, etc.)
# This overrides any matching keys from the backend config.
_MODEL_SERVER_ROOT = Path(__file__).resolve().parents[1]
_MS_CONFIG_DIR = _MODEL_SERVER_ROOT / "config"
_MS_ENV = os.environ.get("ENVIRONMENT", "development")
_MS_CONFIG_FILE = _MS_CONFIG_DIR / f"{_MS_ENV}.yaml"

if _MS_CONFIG_FILE.exists():
    import yaml

    with _MS_CONFIG_FILE.open(encoding="utf-8") as _f:
        _ms_cfg = yaml.safe_load(_f) or {}

    def _flatten_to_env(data: dict, prefix: str = "") -> None:
        for key, value in data.items():
            flat_key = f"{prefix}_{key}" if prefix else str(key)
            if isinstance(value, dict):
                _flatten_to_env(value, flat_key)
                continue
            env_key = flat_key.upper()
            if env_key not in os.environ:
                os.environ[env_key] = str(value)

    _flatten_to_env(_ms_cfg)


# ── Settings model ──────────────────────────────────────────────────────

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
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
    embedding_max_model_len: int = 32768

    # Rerank model
    rerank_model_id: str = "BAAI/bge-reranker-v2-m3"

    # LLM model (placeholder — for future local LLM)
    llm_model_id: str = ""

    # vllm shared settings
    vllm_gpu_memory_utilization: float = 0.9
    embedding_gpu_memory_utilization: float = 0.9
    rerank_gpu_memory_utilization: float = 0.9

    # Document parsing (MinerU)
    doc_parse_backend: str = "vlm"
    doc_parse_gpu_memory_utilization: float = 0.9
    doc_parse_model_path: str = "opendatalab/MinerU2.5-Pro-2604-1.2B"


@lru_cache(maxsize=1)
def get_config() -> Settings:
    return Settings()
