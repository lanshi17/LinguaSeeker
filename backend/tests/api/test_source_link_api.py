"""Tests for source link API routes."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_bilingual_span(async_client: AsyncClient):
    """GET /api/v1/source-link/{id}/bilingual returns bilingual span."""
    from src.core.visualize_evidence_with_expert_in_loop.contracts import BilingualSpan

    evidence_id = uuid4()
    mock_response = BilingualSpan(
        canonical_evidence_id=evidence_id,
        original_track=None,
        translated_track=None,
        alignment_confidence=None,
    )

    with patch("src.api.v1.source_link.get_phase4_factory") as mock_factory:
        mock_linker = MagicMock()
        mock_linker.get_bilingual_span = AsyncMock(return_value=mock_response)
        mock_factory.return_value.create_source_linker.return_value = mock_linker

        response = await async_client.get(
            f"/api/v1/source-link/{evidence_id}/bilingual"
        )
        assert response.status_code == 200
        assert response.json()["canonical_evidence_id"] == str(evidence_id)
