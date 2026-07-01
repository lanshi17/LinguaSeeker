"""Tests for get_db_session commit/rollback behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_get_db_session_commits_on_success():
    """get_db_session commits the session when the route handler succeeds.

    Uses a real FastAPI route to exercise the full yield-dependency lifecycle,
    because aclose() on an async generator does NOT execute code after yield
    the same way FastAPI's dependency injection does.
    """
    from fastapi import Depends, FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.api.deps import get_db_session

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    test_app = FastAPI()

    @test_app.post("/test-write")
    async def test_write(session: AsyncSession = Depends(get_db_session)):
        # Simulate a write operation (service calls flush internally)
        session.add(MagicMock())
        return {"ok": True}

    with patch("src.api.deps.get_session_factory", return_value=mock_factory):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/test-write")
            assert resp.status_code == 200

    mock_session.commit.assert_awaited_once()
    mock_session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_db_session_rollbacks_on_exception():
    """get_db_session rolls back when the route handler raises."""
    from fastapi import Depends, FastAPI, HTTPException
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.api.deps import get_db_session

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    test_app = FastAPI()

    @test_app.post("/test-fail")
    async def test_fail(session: AsyncSession = Depends(get_db_session)):
        raise HTTPException(status_code=500, detail="boom")

    @test_app.exception_handler(500)
    async def handler(request, exc):
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=500, content={"error": str(exc.detail)})

    with patch("src.api.deps.get_session_factory", return_value=mock_factory):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/test-fail")
            assert resp.status_code == 500

    mock_session.rollback.assert_awaited_once()
    mock_session.commit.assert_not_awaited()
