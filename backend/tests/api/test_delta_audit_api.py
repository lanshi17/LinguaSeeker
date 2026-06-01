"""Tests for delta audit API routes."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_audit_events(async_client: AsyncClient):
    """GET /api/v1/delta-audit/ returns audit events."""
    with patch("src.api.v1.delta_audit.get_phase4_factory") as mock_factory:
        mock_service = MagicMock()
        mock_service.list_audit_events = AsyncMock(return_value=[])
        mock_factory.return_value.delta_audit = mock_service

        response = await async_client.get("/api/v1/delta-audit/")
        assert response.status_code == 200
        assert response.json() == []
