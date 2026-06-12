"""Tests for health check graceful degradation."""

import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_redis_health_check_returns_false_on_connection_refused():
    """Redis check should return False, not raise."""
    from src.utils.health import _check_redis

    with patch("src.api.wiring.get_redis_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.ping.side_effect = ConnectionError("Error 111")
        mock_get.return_value = mock_client
        result = await _check_redis()
        assert result is False


@pytest.mark.asyncio
async def test_redis_health_check_skips_when_client_none():
    """Redis check should skip gracefully when client is None."""
    from src.utils.health import _check_redis

    with patch("src.api.wiring.get_redis_client", return_value=None):
        result = await _check_redis()
        assert result is False


@pytest.mark.asyncio
async def test_redis_health_check_logs_at_debug_not_warning(caplog):
    """Redis failure should log at DEBUG, not WARNING, to avoid log spam."""
    from src.utils.health import _check_redis

    with patch("src.api.wiring.get_redis_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.ping.side_effect = ConnectionError("Error 111")
        mock_get.return_value = mock_client
        with caplog.at_level("WARNING"):
            await _check_redis()
    assert not caplog.records  # No WARNING logged
