"""Tests for _try_startup_lock connection lifecycle."""

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture(autouse=True)
def reset_lock_global():
    """Reset module-level global between tests to prevent stale state."""
    import app.main
    app.main._startup_lock_raw_conn = None
    yield
    app.main._startup_lock_raw_conn = None


@pytest.mark.asyncio
async def test_startup_lock_closes_connection_on_sql_error():
    """raw_conn must be closed even when SQL execution fails."""
    from app.main import _try_startup_lock

    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_conn.exec_driver_sql = AsyncMock(side_effect=RuntimeError("SQL failed"))
    mock_conn.close = AsyncMock()
    mock_engine.raw_connection = AsyncMock(return_value=mock_conn)

    result = await _try_startup_lock(mock_engine)

    assert result is True
    mock_conn.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_startup_lock_closes_connection_when_not_acquired():
    """raw_conn must be closed when advisory lock is not acquired."""
    from app.main import _try_startup_lock

    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_result = MagicMock()
    mock_result.fetchone.return_value = (False,)
    mock_conn.exec_driver_sql = AsyncMock(return_value=mock_result)
    mock_conn.close = AsyncMock()
    mock_engine.raw_connection = AsyncMock(return_value=mock_conn)

    result = await _try_startup_lock(mock_engine)

    assert result is False
    mock_conn.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_startup_lock_keeps_connection_when_acquired():
    """raw_conn must NOT be closed when advisory lock is acquired."""
    from app.main import _try_startup_lock

    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_result = MagicMock()
    mock_result.fetchone.return_value = (True,)
    mock_conn.exec_driver_sql = AsyncMock(return_value=mock_result)
    mock_conn.close = AsyncMock()
    mock_engine.raw_connection = AsyncMock(return_value=mock_conn)

    result = await _try_startup_lock(mock_engine)

    assert result is True
    mock_conn.close.assert_not_awaited()
