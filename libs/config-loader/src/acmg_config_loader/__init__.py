"""acmg-config-loader — shared layered YAML config loader."""

from acmg_config_loader.loader import (
    ConfigData,
    load_backend_config_into_env,
)

__all__ = ["ConfigData", "load_backend_config_into_env"]
