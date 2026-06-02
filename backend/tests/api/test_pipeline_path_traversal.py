"""Tests for pipeline upload path traversal prevention."""
from __future__ import annotations

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_upload_strips_directory_from_filename():
    """POST /api/v1/pipeline/run should strip directory components from filename."""
    small_content = base64.b64encode(b"test content").decode()

    with patch("src.core.config.get_config") as mock_cfg, \
         patch("src.api.auth.get_config", mock_cfg), \
         patch("src.utils.health.check_all_connections", new_callable=AsyncMock,
               return_value=AsyncMock(failed_services=AsyncMock(return_value=[]))), \
         patch("src.api.v1.pipeline.get_pipeline_runner") as mock_runner:

        from src.core.config import Settings
        mock_cfg.return_value = Settings(api_key="test-secret")

        captured_state = {}
        def capture_start(state):
            captured_state["upload_file_path"] = state.upload_file_path
            from unittest.mock import MagicMock
            return MagicMock(add_done_callback=lambda cb: None)

        mock_runner.return_value.is_running_for_source = MagicMock(return_value=False)
        mock_runner.return_value.start = capture_start

        from app.main import create_app
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/pipeline/run",
                json={
                    "source_type": "local",
                    "mode": "full",
                    "content_base64": small_content,
                    "filename": "../../etc/passwd",
                },
                headers={"X-API-Key": "test-secret"},
            )
            assert resp.status_code == 202

            upload_path = captured_state["upload_file_path"]
            assert "../" not in upload_path
            assert "etc/passwd" not in upload_path
            assert upload_path.endswith("passwd")


@pytest.mark.asyncio
async def test_upload_strips_windows_directory_from_filename():
    """POST /api/v1/pipeline/run should strip Windows-style path components."""
    small_content = base64.b64encode(b"test content").decode()

    with patch("src.core.config.get_config") as mock_cfg, \
         patch("src.api.auth.get_config", mock_cfg), \
         patch("src.utils.health.check_all_connections", new_callable=AsyncMock,
               return_value=AsyncMock(failed_services=AsyncMock(return_value=[]))), \
         patch("src.api.v1.pipeline.get_pipeline_runner") as mock_runner:

        from src.core.config import Settings
        mock_cfg.return_value = Settings(api_key="test-secret")

        captured_state = {}
        def capture_start(state):
            captured_state["upload_file_path"] = state.upload_file_path
            return MagicMock(add_done_callback=lambda cb: None)

        mock_runner.return_value.is_running_for_source = MagicMock(return_value=False)
        mock_runner.return_value.start = capture_start

        from app.main import create_app
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/pipeline/run",
                json={
                    "source_type": "local",
                    "mode": "full",
                    "content_base64": small_content,
                    "filename": "..\\..\\etc\\passwd",
                },
                headers={"X-API-Key": "test-secret"},
            )
            assert resp.status_code == 202

            upload_path = captured_state["upload_file_path"]
            assert "\\" not in upload_path
            assert "../" not in upload_path
            assert upload_path.endswith("passwd")
