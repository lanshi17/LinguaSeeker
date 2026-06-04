"""Model server configuration — reads config-dev.yaml and env vars."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_SERVICE_ROOT = Path(__file__).resolve().parents[1]
_BACKEND_ROOT = Path(__file__).resolve().parents[3]
# ── YAML config loader (shared with backend) ────────────────────────────

def _load_yaml_config() -> None:
    """Load backend/config-dev.yaml, set as env vars (env vars take precedence)."""
    try:
        import yaml
    except ImportError:
        return

    config_path = _BACKEND_ROOT / "config-dev.yaml"
    if not config_path.exists():
        return

    with open(config_path) as f:
        data = yaml.safe_load(f) or {}

    for key, value in data.items():
        env_key = str(key).upper()
        if env_key not in os.environ:
            os.environ[env_key] = str(value)


_load_yaml_config()




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

    # VLM model (MinerU)
    vlm_model_id: str = ""
    vlm_image_analysis: bool = False

    # vllm shared settings
    vllm_gpu_memory_utilization: float = 0.9
    embedding_gpu_memory_utilization: float = 0.9
    rerank_gpu_memory_utilization: float = 0.9
    vlm_gpu_memory_utilization: float = 0.9


@lru_cache(maxsize=1)
def get_config() -> Settings:
    return Settings()
