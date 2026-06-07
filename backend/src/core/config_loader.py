"""Shared loader for layered backend configuration files."""

from __future__ import annotations

from collections.abc import MutableMapping
import os
from pathlib import Path
from typing import Any, TypeAlias


ConfigData: TypeAlias = dict[str, Any]


def load_backend_config_into_env(
    backend_root: Path,
    environ: MutableMapping[str, str] | None = None,
) -> None:
    """Load ``backend/config`` layered YAML values into environment variables.

    File loading order is ``defaults/main.yaml``, ``environments/<env>.yaml``,
    then ``vault/<env>.yaml``. Existing environment variables always win.
    """
    target_env = environ if environ is not None else os.environ
    try:
        import yaml
    except ImportError:
        return

    config_dir = backend_root / "config"
    environment = target_env.get("ENVIRONMENT", "development")
    merged: ConfigData = {}

    for path in (
        config_dir / "defaults" / "main.yaml",
        config_dir / "environments" / f"{environment}.yaml",
        config_dir / "vault" / f"{environment}.yaml",
    ):
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as f:
            layer = yaml.safe_load(f) or {}
        if not isinstance(layer, dict):
            raise ValueError(f"Configuration layer must be a mapping: {path}")
        merged = _deep_merge(merged, layer)

    _flatten_and_set_env(merged, target_env)


def _deep_merge(base: ConfigData, override: ConfigData) -> ConfigData:
    """Recursively merge an arbitrary YAML mapping tree."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _flatten_and_set_env(data: ConfigData, environ: MutableMapping[str, str], prefix: str = "") -> None:
    """Flatten nested YAML keys and set missing uppercase env vars."""
    for key, value in data.items():
        flat_key = f"{prefix}_{key}" if prefix else str(key)
        if isinstance(value, dict):
            _flatten_and_set_env(value, environ, flat_key)
            continue

        env_key = flat_key.upper()
        if env_key not in environ:
            if isinstance(value, list):
                # Join lists with commas for pydantic-settings list fields
                environ[env_key] = ",".join(str(v) for v in value)
            else:
                environ[env_key] = str(value)
