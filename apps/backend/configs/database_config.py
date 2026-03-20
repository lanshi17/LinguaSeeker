"""Compatibility wrapper for legacy `configs.database_config` imports."""

from src.configs.database_config import DatabaseConfig, MinIOConfig, database_config

__all__ = ["DatabaseConfig", "MinIOConfig", "database_config"]
