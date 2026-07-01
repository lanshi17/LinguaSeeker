"""Tests for startup health checks."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.utils.health import HealthResult, check_all_connections


@pytest.mark.asyncio
async def test_check_all_returns_health_result():
    """check_all_connections returns a HealthResult when services are up."""
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()

    @asynccontextmanager
    async def _mock_connect():
        yield mock_conn

    mock_engine = MagicMock()
    mock_engine.connect = _mock_connect

    mock_redis = AsyncMock()
    mock_redis.ping.return_value = True

    with (
        patch("src.api.wiring.get_engine", return_value=mock_engine),
        patch("src.api.wiring.get_redis_client", return_value=mock_redis),
    ):
        result = await check_all_connections()
        assert isinstance(result, HealthResult)
        assert result.postgres is True
        assert result.redis is True
        assert result.all_ok() is True
        assert result.failed_services() == []


@pytest.mark.asyncio
async def test_check_redis_uses_wiring_singleton() -> None:
    """Health check reuses the wiring Redis singleton, not a throwaway client."""
    from unittest.mock import AsyncMock, patch

    mock_client = AsyncMock()
    mock_client.ping.return_value = True

    with patch("src.api.wiring.get_redis_client", return_value=mock_client):
        from src.utils.health import _check_redis

        result = await _check_redis()

    assert result is True
    mock_client.ping.assert_awaited_once()
    # Must NOT close the singleton client
    mock_client.aclose.assert_not_awaited()


@pytest.mark.asyncio
async def test_check_all_reports_postgres_failure():
    """PostgreSQL failure should be reported as False."""

    @asynccontextmanager
    async def _mock_connect():
        raise ConnectionError("refused")
        yield  # pragma: no cover

    mock_engine = MagicMock()
    mock_engine.connect = _mock_connect

    mock_redis = AsyncMock()
    mock_redis.ping.return_value = True

    with (
        patch("src.api.wiring.get_engine", return_value=mock_engine),
        patch("src.api.wiring.get_redis_client", return_value=mock_redis),
    ):
        result = await check_all_connections()
        assert result.postgres is False
        assert result.redis is True
        assert result.all_ok() is False
        assert "postgres" in result.failed_services()
