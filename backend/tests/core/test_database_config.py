"""Tests for database-related application configuration."""
from __future__ import annotations

from src.core.config import Settings


def test_postgresql_and_redis_nested_config() -> None:
    """Settings exposes nested PostgreSQL and Redis configuration."""
    settings = Settings()

    assert settings.postgresql.host == "127.0.0.1"
    assert settings.postgresql.port == 5432
    assert settings.postgresql.db == "acmg_ps3"
    assert settings.postgresql.schema_ == "acmg_app"
    assert settings.postgresql.user == ""
    assert settings.postgresql.password == ""
    assert settings.postgresql.pool_size == 20
    assert settings.postgresql.max_overflow == 30

    assert settings.redis.host == "localhost"
    assert settings.redis.port == 6379
    assert settings.redis.password == ""
    assert settings.redis.db == 0
    assert settings.redis.max_connections == 20


def test_postgresql_dsn_helper_uses_async_sqlalchemy_driver(monkeypatch) -> None:
    """Settings derives an async SQLAlchemy PostgreSQL DSN."""
    monkeypatch.setenv("POSTGRES_USER", "db_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p@ss word")
    monkeypatch.setenv("POSTGRES_HOST", "db.internal")
    monkeypatch.setenv("POSTGRES_PORT", "55432")
    monkeypatch.setenv("POSTGRES_DB", "acmg_test")

    settings = Settings()

    assert settings.postgresql_dsn == "postgresql+asyncpg://db_user:p%40ss%20word@db.internal:55432/acmg_test"
