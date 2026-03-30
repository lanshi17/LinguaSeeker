"""Compatibility wrapper for legacy `configs.app_config` imports."""

from src.config import AppConfig, app_config

__all__ = ["AppConfig", "app_config"]
