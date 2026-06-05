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
    """Load configuration from layered YAML files or legacy config-dev.yaml.
    
    New layered loading (preferred):
      1. config/defaults/main.yaml          (base structural defaults)
      2. config/environments/<env>.yaml     (environment-specific overrides)
      3. config/vault/<env>.yaml            (secrets, git-ignored)
    
    Legacy fallback:
      - config-dev.yaml (if config/ directory doesn't exist)
    
    Environment variables take precedence over all YAML values.
    """
    # Check for new layered config structure
    config_dir = _BACKEND_ROOT / "config"
    if config_dir.exists() and (config_dir / "defaults" / "main.yaml").exists():
        _load_layered_yaml_config()
    else:
        # Legacy fallback: load config-dev.yaml
        _load_legacy_yaml_config()


def _load_layered_yaml_config() -> None:
    """Load from layered config/ directory structure."""
    import os
    try:
        import yaml
    except ImportError:
        return
    
    config_dir = _BACKEND_ROOT / "config"
    
    # Determine environment (default to 'development')
    environment = os.environ.get("ENVIRONMENT", "development")
    
    merged = {}
    
    # Layer 1: defaults/main.yaml
    defaults_path = config_dir / "defaults" / "main.yaml"
    if defaults_path.exists():
        with open(defaults_path) as f:
            defaults = yaml.safe_load(f) or {}
        merged = _deep_merge(merged, defaults)
    
    # Layer 2: environments/<env>.yaml
    env_path = config_dir / "environments" / f"{environment}.yaml"
    if env_path.exists():
        with open(env_path) as f:
            env_config = yaml.safe_load(f) or {}
        merged = _deep_merge(merged, env_config)
    
    # Layer 3: vault/<env>.yaml (secrets)
    vault_path = config_dir / "vault" / f"{environment}.yaml"
    if vault_path.exists():
        with open(vault_path) as f:
            vault_secrets = yaml.safe_load(f) or {}
        merged = _deep_merge(merged, vault_secrets)
    
    # Flatten nested structure and set as env vars
    _flatten_and_set_env(merged)


def _load_legacy_yaml_config() -> None:
    """Legacy fallback: load from config-dev.yaml."""
    import os
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


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override dict into base dict."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _flatten_and_set_env(data: dict, prefix: str = "") -> None:
    """Flatten nested dict and set as uppercase env vars."""
    import os
    
    for key, value in data.items():
        # Build the flat key name
        flat_key = f"{prefix}_{key}" if prefix else key
        
        if isinstance(value, dict):
            # Recurse into nested dicts
            _flatten_and_set_env(value, flat_key)
        else:
            # Set as uppercase env var if not already set
            env_key = flat_key.upper()
            if env_key not in os.environ:
                os.environ[env_key] = str(value)


def _load_layered_yaml_config() -> None:
    """Load from layered config/ directory structure."""
    import os
    try:
        import yaml
    except ImportError:
        return
    
    config_dir = _BACKEND_ROOT / "config"
    
    # Determine environment (default to 'development')
    environment = os.environ.get("ENVIRONMENT", "development")
    
    merged = {}
    
    # Layer 1: defaults/main.yaml
    defaults_path = config_dir / "defaults" / "main.yaml"
    if defaults_path.exists():
        with open(defaults_path) as f:
            defaults = yaml.safe_load(f) or {}
        merged = _deep_merge(merged, defaults)
    
    # Layer 2: environments/<env>.yaml
    env_path = config_dir / "environments" / f"{environment}.yaml"
    if env_path.exists():
        with open(env_path) as f:
            env_config = yaml.safe_load(f) or {}
        merged = _deep_merge(merged, env_config)
    
    # Layer 3: vault/<env>.yaml (secrets)
    vault_path = config_dir / "vault" / f"{environment}.yaml"
    if vault_path.exists():
        with open(vault_path) as f:
            vault_secrets = yaml.safe_load(f) or {}
        merged = _deep_merge(merged, vault_secrets)
    
    # Flatten nested structure and set as env vars
    _flatten_and_set_env(merged)


def _load_legacy_yaml_config() -> None:
    """Legacy fallback: load from config-dev.yaml."""
    import os
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


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override dict into base dict."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _flatten_and_set_env(data: dict, prefix: str = "") -> None:
    """Flatten nested dict and set as uppercase env vars."""
    import os
    
    for key, value in data.items():
        # Build the flat key name
        flat_key = f"{prefix}_{key}" if prefix else key
        
        if isinstance(value, dict):
            # Recurse into nested dicts
            _flatten_and_set_env(value, flat_key)
        else:
            # Set as uppercase env var if not already set
            env_key = flat_key.upper()
            if env_key not in os.environ:
                os.environ[env_key] = str(value)
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
