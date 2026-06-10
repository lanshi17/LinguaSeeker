"""Backward-compat shim — actual implementation lives in libs/config-loader.

This module is kept so existing call sites in backend/src/ keep working. New
code should import from ``acmg_config_loader`` directly.
"""

from acmg_config_loader import ConfigData, load_backend_config_into_env

__all__ = ["ConfigData", "load_backend_config_into_env"]
