"""Integration test: full app startup, lifespan, and health check.

Focuses on startup lifecycle — error handler behavior is covered in
test_error_handlers.py (Task 5).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.utils.health import HealthResult


@pytest_asyncio.fixture
async def integration_client():
    """Async HTTP client with config and health checks mocked."""
    with (
        patch("src.core.config.get_config") as mock_cfg,
        patch(
            "src.utils.health.check_all_connections",
            new_callable=AsyncMock,
            return_value=HealthResult(postgres=True, redis=True),
        ),
    ):
        from src.core.config import Settings
        mock_cfg.return_value = Settings()
        from app.main import create_app
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


@pytest.mark.asyncio
async def test_app_starts_and_health_returns_ok(integration_client: AsyncClient):
    """The app should start up (lifespan runs) and respond to /health."""
    resp = await integration_client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_request_id_on_all_responses(integration_client: AsyncClient):
    """X-Request-ID header should appear on all responses (success and error)."""
    success = await integration_client.get("/health")
    assert "x-request-id" in success.headers

    error = await integration_client.get("/api/v1/nonexistent")
    assert "x-request-id" in error.headers
