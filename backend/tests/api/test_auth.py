"""Tests for API key authentication."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def _mock_config_with_api_key():
    """Provide config with API_KEY set."""
    with patch("src.core.config.get_config") as mock_cfg:
        from src.core.config import Settings
        mock_cfg.return_value = Settings(api_key="test-secret-key")
        yield mock_cfg


@pytest.mark.asyncio
async def test_write_route_rejected_without_api_key(_mock_config_with_api_key):
    """Write routes should return 401 when API_KEY is set but not provided."""
    with (
        patch("src.utils.health.check_all_connections", new_callable=AsyncMock,
              return_value=MagicMock(failed_services=MagicMock(return_value=[]))),
    ):
        from app.main import create_app
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.patch(
                "/api/v1/evidence/00000000-0000-0000-0000-000000000000",
                json={"fields": {"gene": "BRCA1"}},
            )
            assert resp.status_code == 401


@pytest.mark.asyncio
async def test_write_route_accepted_with_valid_api_key(_mock_config_with_api_key):
    """Write routes should accept requests with valid X-API-Key header."""
    from sqlalchemy.ext.asyncio import AsyncSession

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.commit = AsyncMock()

    with (
        patch("src.utils.health.check_all_connections", new_callable=AsyncMock,
              return_value=MagicMock(failed_services=MagicMock(return_value=[]))),
        patch("src.api.v1.evidence.get_phase4_factory") as mock_factory,
        patch("src.api.deps.get_session_factory") as mock_sf,
    ):
        mock_sf.return_value = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_session),
                __aexit__=AsyncMock(return_value=False),
            )
        )

        from src.core.visualize_evidence_with_expert_in_loop.feedback_service import PatchResult
        from src.core.visualize_evidence_with_expert_in_loop.contracts import ReviewStatus

        mock_service = MagicMock()
        mock_service.patch_evidence = AsyncMock(return_value=PatchResult(
            canonical_evidence_id="00000000-0000-0000-0000-000000000000",
            old_status=ReviewStatus.PROVISIONAL,
            new_status=ReviewStatus.CORRECTED,
            deltas=1,
            field_deltas=[],
        ))
        mock_factory.return_value.create_feedback_service.return_value = mock_service

        from app.main import create_app
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.patch(
                "/api/v1/evidence/00000000-0000-0000-0000-000000000000",
                json={"fields": {"gene": "BRCA1"}},
                headers={"X-API-Key": "test-secret-key"},
            )
            assert resp.status_code == 200


@pytest.mark.asyncio
async def test_read_routes_open_when_no_api_key_configured():
    """When API_KEY is empty, all routes are accessible without auth."""
    with (
        patch("src.core.config.get_config") as mock_cfg,
        patch("src.utils.health.check_all_connections", new_callable=AsyncMock,
              return_value=MagicMock(failed_services=MagicMock(return_value=[]))),
    ):
        from src.core.config import Settings
        mock_cfg.return_value = Settings(api_key="")  # No key configured

        from app.main import create_app
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")
            assert resp.status_code == 200
