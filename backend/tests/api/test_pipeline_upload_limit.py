"""Tests for pipeline upload size limits."""
from __future__ import annotations

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_upload_rejects_oversized_files():
    """POST /api/v1/pipeline/run should reject files exceeding size limit."""
    large_content = base64.b64encode(b"x" * (101 * 1024 * 1024)).decode()

    with patch("src.core.config.get_config") as mock_cfg, \
         patch("src.api.auth.get_config", mock_cfg), \
         patch("src.utils.health.check_all_connections", new_callable=AsyncMock,
               return_value=AsyncMock(failed_services=AsyncMock(return_value=[]))), \
         patch("src.api.v1.pipeline.get_pipeline_runner") as mock_get_runner:
        from src.core.config import Settings
        mock_cfg.return_value = Settings(
            api_key="test-secret",
            mineru_max_file_size_mb=100,
        )

        mock_runner = MagicMock()
        mock_runner.is_running_for_source = MagicMock(return_value=False)
        mock_get_runner.return_value = mock_runner

        from app.main import create_app
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/pipeline/run",
                json={
                    "source_type": "local",
                    "mode": "full",
                    "content_base64": large_content,
                    "filename": "large.pdf",
                },
                headers={"X-API-Key": "test-secret"},
            )
            assert resp.status_code == 413
            assert "File too large" in resp.json()["error"]["message"]
