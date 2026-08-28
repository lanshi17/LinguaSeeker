"""Shared fixtures for API tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.utils.health import HealthResult


@pytest_asyncio.fixture
async def async_client():
    """Create an async HTTP client for testing FastAPI endpoints."""
    from src.core.config import Settings

    mock_settings = Settings(api_key="")  # Auth disabled for tests

    with (
        patch("src.core.config.get_config") as mock_cfg,
        patch("src.api.auth.get_config", mock_cfg),
        patch(
            "src.utils.health.check_all_connections",
            new_callable=AsyncMock,
            return_value=HealthResult(postgres=True, redis=True),
        ),
    ):
        mock_cfg.return_value = mock_settings
        from app.main import create_app

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


@pytest_asyncio.fixture(autouse=True)
def _dummy_session_factory():
    """Provide a stub session factory for routes depending on get_db_session.

    API tests run without ``wire_dependencies()`` (no DB); routes that use
    the session dependency would otherwise raise "Session factory not
    initialized". Tests needing a real/mock session override this patch
    themselves (inner ``patch()`` takes precedence).
    """
    mock_session = AsyncMock()
    async_ctx = AsyncMock()
    async_ctx.__aenter__.return_value = mock_session
    factory = MagicMock(return_value=async_ctx)
    with patch("src.api.deps.get_session_factory", return_value=factory):
        yield
