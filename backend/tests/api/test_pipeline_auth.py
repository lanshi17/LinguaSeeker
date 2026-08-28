"""Tests for pipeline route authentication.

Anonymous requests fall back to the public account by design (the app
supports guest runs); the enforceable guarantee is that an *invalid*
X-API-Key is rejected with 401 before any pipeline logic runs.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_pipeline_run_rejects_invalid_api_key():
    """POST /api/v1/pipeline/run returns 401 for a wrong X-API-Key."""
    with (
        patch("src.core.config.get_config") as mock_cfg,
        patch("src.api.auth.get_config") as mock_auth_cfg,
        patch(
            "src.utils.health.check_all_connections",
            new_callable=AsyncMock,
            return_value=AsyncMock(failed_services=AsyncMock(return_value=[])),
        ),
    ):
        from src.core.config import Settings

        mock_auth_cfg.return_value = Settings(api_key="test-secret")
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
                headers={"X-API-Key": "wrong-key"},
            )
            assert resp.status_code == 401


@pytest.mark.asyncio
async def test_pipeline_status_rejects_invalid_api_key():
    """GET /api/v1/pipeline/runs/{id}/status returns 401 for a wrong X-API-Key."""
    with (
        patch("src.core.config.get_config") as mock_cfg,
        patch("src.api.auth.get_config") as mock_auth_cfg,
        patch(
            "src.utils.health.check_all_connections",
            new_callable=AsyncMock,
            return_value=AsyncMock(failed_services=AsyncMock(return_value=[])),
        ),
    ):
        from src.core.config import Settings

        mock_cfg.return_value = Settings(api_key="test-secret")
        mock_auth_cfg.return_value = Settings(api_key="test-secret")

        from app.main import create_app

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/pipeline/runs/test-run-id/status",
                headers={"X-API-Key": "wrong-key"},
            )
            assert resp.status_code == 401
