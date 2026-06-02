"""Tests for API rate limiting."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.utils.health import HealthResult


@pytest.mark.asyncio
async def test_pipeline_run_rate_limited():
    """POST /api/v1/pipeline/run should return 429 after exceeding 10/minute."""
    from src.core.config import Settings
    from src.api.rate_limit import limiter

    # Clear any rate limit state from previous tests
    limiter._storage.reset()

    mock_settings = Settings(api_key="")

    with (
        patch("src.core.config.get_config") as mock_cfg,
        patch("src.api.auth.get_config", mock_cfg),
        patch(
            "src.utils.health.check_all_connections",
            new_callable=AsyncMock,
            return_value=HealthResult(postgres=True, redis=True),
        ),
        patch("src.api.v1.pipeline.get_pipeline_runner") as mock_get_runner,
    ):
        mock_cfg.return_value = mock_settings

        mock_runner = MagicMock()
        mock_runner.start = MagicMock(return_value=MagicMock())
        mock_runner.is_running_for_source = MagicMock(return_value=False)
        mock_get_runner.return_value = mock_runner

        from app.main import create_app

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            responses = []
            for _ in range(11):
                mock_file = AsyncMock()
                mock_file.__aenter__ = AsyncMock(return_value=mock_file)
                mock_file.__aexit__ = AsyncMock(return_value=False)
                mock_file.write = AsyncMock()
                with patch("src.api.v1.pipeline.aiofiles.open", return_value=mock_file):
                    resp = await client.post(
                        "/api/v1/pipeline/run",
                        json={
                            "source_type": "online",
                            "mode": "full",
                            "query": "BRCA1",
                        },
                    )
                responses.append(resp.status_code)

            assert responses[:10] == [202] * 10
            assert responses[10] == 429
