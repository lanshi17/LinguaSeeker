"""Tests for pipeline route authentication."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_pipeline_run_requires_api_key():
    """POST /api/v1/pipeline/run should require X-API-Key when API_KEY is configured."""
    with (
        patch("src.core.config.get_config") as mock_cfg,
        patch(
            "src.utils.health.check_all_connections",
            new_callable=AsyncMock,
            return_value=AsyncMock(failed_services=AsyncMock(return_value=[])),
        ),
    ):
        from src.core.config import Settings

        mock_cfg.return_value = Settings(api_key="test-secret")

        from app.main import create_app

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/pipeline/run",
                json={
                    "source_type": "online",
                    "mode": "full",
                    "query": "BRCA1",
                },
            )
            assert resp.status_code == 401


@pytest.mark.asyncio
async def test_pipeline_status_requires_api_key():
    """GET /api/v1/pipeline/runs/{id}/status should require X-API-Key."""
    with (
        patch("src.core.config.get_config") as mock_cfg,
        patch(
            "src.utils.health.check_all_connections",
            new_callable=AsyncMock,
            return_value=AsyncMock(failed_services=AsyncMock(return_value=[])),
        ),
    ):
        from src.core.config import Settings

        mock_cfg.return_value = Settings(api_key="test-secret")

        from app.main import create_app

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/pipeline/runs/test-run-id/status",
            )
            assert resp.status_code == 401
