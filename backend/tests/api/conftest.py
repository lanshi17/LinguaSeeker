"""Shared fixtures for API tests."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

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
