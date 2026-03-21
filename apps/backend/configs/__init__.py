"""Backward-compatible top-level config package wrappers."""

from .app_config import AppConfig, app_config
from .database_config import DatabaseConfig, MinIOConfig, database_config

__all__ = [
    "AppConfig",
    "DatabaseConfig",
    "MinIOConfig",
    "app_config",
    "database_config",
]
