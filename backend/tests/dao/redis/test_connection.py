"""Tests for Redis connection helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def test_build_redis_client_passes_config_params() -> None:
    """build_redis_client forwards all config values to redis.asyncio.Redis."""
    from src.dao.redis.connection import build_redis_client

    fake_cfg = MagicMock()
    fake_cfg.redis.host = "127.0.0.1"
    fake_cfg.redis.port = 6380
    fake_cfg.redis.password = "s3cret"
    fake_cfg.redis.db = 2
    fake_cfg.redis.max_connections = 10

    with (
        patch("src.dao.redis.connection.get_config", return_value=fake_cfg),
        patch("src.dao.redis.connection.aioredis.Redis") as mock_cls,
    ):
        build_redis_client()

    mock_cls.assert_called_once_with(
        host="127.0.0.1",
        port=6380,
        password="s3cret",
        db=2,
        max_connections=10,
        decode_responses=False,
    )


def test_build_redis_client_passwordless() -> None:
    """build_redis_client converts empty password string to None."""
    from src.dao.redis.connection import build_redis_client

    fake_cfg = MagicMock()
    fake_cfg.redis.host = "localhost"
    fake_cfg.redis.port = 6379
    fake_cfg.redis.password = ""
    fake_cfg.redis.db = 0
    fake_cfg.redis.max_connections = 20

    with (
        patch("src.dao.redis.connection.get_config", return_value=fake_cfg),
        patch("src.dao.redis.connection.aioredis.Redis") as mock_cls,
    ):
        build_redis_client()

    mock_cls.assert_called_once_with(
        host="localhost",
        port=6379,
        password=None,  # empty string coerced to None
        db=0,
        max_connections=20,
        decode_responses=False,
    )


def test_build_redis_client_custom_db() -> None:
    """build_redis_client passes custom db number to Redis constructor."""
    from src.dao.redis.connection import build_redis_client

    fake_cfg = MagicMock()
    fake_cfg.redis.host = "redis.example.com"
    fake_cfg.redis.port = 6379
    fake_cfg.redis.password = "pw"
    fake_cfg.redis.db = 3
    fake_cfg.redis.max_connections = 5

    with (
        patch("src.dao.redis.connection.get_config", return_value=fake_cfg),
        patch("src.dao.redis.connection.aioredis.Redis") as mock_cls,
    ):
        build_redis_client()

    _, kwargs = mock_cls.call_args
    assert kwargs["db"] == 3
    assert kwargs["host"] == "redis.example.com"
    assert kwargs["max_connections"] == 5


def test_build_redis_client_uses_settings_param() -> None:
    """build_redis_client accepts explicit Settings, skipping get_config()."""
    from src.dao.redis.connection import build_redis_client

    fake_cfg = MagicMock()
    fake_cfg.redis.host = "custom-host"
    fake_cfg.redis.port = 6379
    fake_cfg.redis.password = ""
    fake_cfg.redis.db = 0
    fake_cfg.redis.max_connections = 10

    with patch("src.dao.redis.connection.aioredis.Redis") as mock_cls:
        build_redis_client(settings=fake_cfg)

    _, kwargs = mock_cls.call_args
    assert kwargs["host"] == "custom-host"


def test_get_redis_client_returns_none_before_init() -> None:
    """get_redis_client returns None before wire_dependencies runs."""
    import src.api.wiring as wiring

    # Force-reset the module singleton
    wiring._redis_client = None
    assert wiring.get_redis_client() is None


@pytest.mark.asyncio
async def test_dispose_redis_closes_client() -> None:
    """dispose_redis closes the client and resets the singleton."""
    import src.api.wiring as wiring

    mock_client = AsyncMock()
    wiring._redis_client = mock_client

    await wiring.dispose_redis()
    mock_client.aclose.assert_awaited_once()
    assert wiring._redis_client is None
