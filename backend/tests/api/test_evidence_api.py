"""Tests for evidence API routes."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_patch_evidence_returns_updated_card(async_client: AsyncClient):
    """PATCH /api/v1/evidence/{id} applies patch and returns result."""
    from src.core.visualize_evidence_with_expert_in_loop.contracts import ReviewStatus
    from src.core.visualize_evidence_with_expert_in_loop.feedback_service import PatchResult

    evidence_id = uuid4()
    mock_result = PatchResult(
        canonical_evidence_id=evidence_id,
        old_status=ReviewStatus.PROVISIONAL,
        new_status=ReviewStatus.CORRECTED,
        deltas=1,
        field_deltas=[],
    )

    # Patch in the route module where get_phase4_factory is bound
    with patch("src.api.v1.evidence.get_phase4_factory") as mock_factory:
        mock_service = MagicMock()
        mock_service.patch_evidence = AsyncMock(return_value=mock_result)
        mock_factory.return_value.create_feedback_service.return_value = mock_service

        response = await async_client.patch(
            f"/api/v1/evidence/{evidence_id}",
            json={"fields": {"gene": "BRCA1"}, "change_reason": "test"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["canonical_evidence_id"] == str(evidence_id)
        assert data["new_status"] == "corrected"


@pytest.mark.asyncio
async def test_patch_evidence_404_for_unknown(async_client: AsyncClient):
    """PATCH /api/v1/evidence/{id} returns 404 for unknown evidence."""
    from sqlalchemy.exc import NoResultFound

    with patch("src.api.v1.evidence.get_phase4_factory") as mock_factory:
        mock_service = MagicMock()
        mock_service.patch_evidence = AsyncMock(side_effect=NoResultFound())
        mock_factory.return_value.create_feedback_service.return_value = mock_service

        response = await async_client.patch(
            f"/api/v1/evidence/{uuid4()}",
            json={"fields": {"gene": "BRCA1"}},
        )
        assert response.status_code == 404
