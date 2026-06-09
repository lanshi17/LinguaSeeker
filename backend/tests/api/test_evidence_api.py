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


@pytest.mark.asyncio
async def test_get_evidence_group_detail(async_client: AsyncClient):
    """GET /api/v1/evidence/groups/{group_id} returns grouped evidence detail."""
    from src.core.visualize_evidence_with_expert_in_loop.contracts import (
        EvidenceFieldDistribution,
        EvidenceGroupDetailResponse,
    )

    source_document_id = uuid4()
    group_id = "gene=['BRCA1']|variant=['c.68_69delAG']"
    mock_response = EvidenceGroupDetailResponse(
        group_id=group_id,
        source_document_id=source_document_id,
        title="BRCA1 clinical evidence paper",
        gene="BRCA1",
        variant="c.68_69delAG",
        disease="Hereditary breast and ovarian cancer",
        classification="Pathogenic",
        item_count=0,
        avg_confidence=None,
        distribution=EvidenceFieldDistribution(),
        items=[],
        traces=[],
    )

    with patch("src.api.v1.evidence.SearchService") as mock_service_cls:
        mock_service = MagicMock()
        mock_service.get_group_detail = AsyncMock(return_value=mock_response)
        mock_service_cls.return_value = mock_service

        response = await async_client.get("/api/v1/evidence/groups/detail", params={"group_id": group_id})

    assert response.status_code == 200
    data = response.json()
    assert data["group_id"] == group_id
    assert data["title"] == "BRCA1 clinical evidence paper"
    assert data["gene"] == "BRCA1"


@pytest.mark.asyncio
async def test_get_evidence_group_detail_returns_404(async_client: AsyncClient):
    """GET /api/v1/evidence/groups/{group_id} returns 404 when group is missing."""
    from sqlalchemy.exc import NoResultFound

    with patch("src.api.v1.evidence.SearchService") as mock_service_cls:
        mock_service = MagicMock()
        mock_service.get_group_detail = AsyncMock(side_effect=NoResultFound())
        mock_service_cls.return_value = mock_service

        response = await async_client.get("/api/v1/evidence/groups/detail", params={"group_id": "missing-group"})

    assert response.status_code == 404
