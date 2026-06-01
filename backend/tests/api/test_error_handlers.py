"""Tests for global error handlers."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.utils.health import HealthResult


@pytest_asyncio.fixture
async def error_client():
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
async def test_health_endpoint(error_client: AsyncClient):
    resp = await error_client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_unknown_route_returns_structured_404(error_client: AsyncClient):
    resp = await error_client.get("/api/v1/does-not-exist")
    assert resp.status_code == 404
    body = resp.json()
    assert "error" in body
    assert body["error"]["code"] == "NOT_FOUND"
    assert "request_id" in body


@pytest.mark.asyncio
async def test_request_id_in_response_header(error_client: AsyncClient):
    """X-Request-ID header should be present on all responses."""
    resp = await error_client.get("/health")
    assert "x-request-id" in resp.headers


@pytest.mark.asyncio
async def test_custom_request_id_preserved(error_client: AsyncClient):
    """Client-supplied X-Request-ID should be echoed back."""
    resp = await error_client.get("/health", headers={"X-Request-ID": "test-123"})
    assert resp.headers.get("x-request-id") == "test-123"
