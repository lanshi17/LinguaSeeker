"""Compatibility wrapper for legacy `src.configs.database_config` imports."""

from dataclasses import dataclass

from src.config import AppConfig, MinIOConfig


@dataclass
class DatabaseConfig:
    """Legacy wrapper exposing database-related config off the modern AppConfig."""

    minio: MinIOConfig

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        app_cfg = AppConfig.from_env()
        return cls(minio=app_cfg.minio)


database_config = DatabaseConfig.from_env()

__all__ = ["DatabaseConfig", "MinIOConfig", "database_config"]
