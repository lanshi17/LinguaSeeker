"""Tests for database-related application configuration."""
from __future__ import annotations

from src.core.config import Settings


DATABASE_ENV_VARS = (
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_DB",
    "POSTGRES_SCHEMA",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_POOL_SIZE",
    "POSTGRES_MAX_OVERFLOW",
    "REDIS_HOST",
    "REDIS_PORT",
    "REDIS_PASSWORD",
    "REDIS_DB",
    "REDIS_MAX_CONNECTIONS",
)


def test_postgresql_and_redis_nested_config(monkeypatch) -> None:
    """Settings exposes nested PostgreSQL and Redis configuration."""
    for env_var in DATABASE_ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)

    settings = Settings(_env_file=None)

    assert settings.postgresql.host == "127.0.0.1"
    assert settings.postgresql.port == 5432
    assert settings.postgresql.db == "cross_evidence"
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


def test_postgresql_dsn_helper_omits_empty_userinfo() -> None:
    """Settings omits userinfo when no PostgreSQL user is configured."""
    settings = Settings(
        postgres_user="",
        postgres_password="",
        postgres_host="db.internal",
        postgres_port=55432,
        postgres_db="acmg_test",
    )

    assert settings.postgresql_dsn == "postgresql+asyncpg://db.internal:55432/acmg_test"


def test_postgresql_dsn_helper_supports_user_without_password() -> None:
    """Settings keeps the username when no PostgreSQL password is configured."""
    settings = Settings(
        postgres_user="db_user",
        postgres_password="",
        postgres_host="db.internal",
        postgres_port=55432,
        postgres_db="acmg_test",
    )

    assert settings.postgresql_dsn == "postgresql+asyncpg://db_user@db.internal:55432/acmg_test"


def test_postgresql_dsn_helper_escapes_database_name() -> None:
    """Settings escapes special characters in the database component."""
    settings = Settings(
        postgres_user="db_user",
        postgres_password="db_password",
        postgres_host="db.internal",
        postgres_port=55432,
        postgres_db="tenant/db",
    )

    assert settings.postgresql_dsn == "postgresql+asyncpg://db_user:db_password@db.internal:55432/tenant%2Fdb"
