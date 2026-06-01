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


@pytest.mark.asyncio
async def test_get_track_span(async_client: AsyncClient):
    """GET /api/v1/source-link/{id}/{track} returns track span."""
    from src.core.visualize_evidence_with_expert_in_loop.contracts import TrackSpan

    evidence_id = uuid4()
    mock_response = TrackSpan(
        track="original",
        source_span={"text_snippet": "some text", "page": 1},
        block_text="full block text",
        highlight_start=0,
        highlight_end=9,
        page=1,
    )

    with patch("src.api.v1.source_link.get_phase4_factory") as mock_factory:
        mock_linker = MagicMock()
        mock_linker.get_track_span = AsyncMock(return_value=mock_response)
        mock_factory.return_value.create_source_linker.return_value = mock_linker

        response = await async_client.get(
            f"/api/v1/source-link/{evidence_id}/original"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["track"] == "original"
        assert data["block_text"] == "full block text"


@pytest.mark.asyncio
async def test_get_track_span_returns_null_for_missing_track(async_client: AsyncClient):
    """GET /api/v1/source-link/{id}/{track} returns null when track has no span."""
    with patch("src.api.v1.source_link.get_phase4_factory") as mock_factory:
        mock_linker = MagicMock()
        mock_linker.get_track_span = AsyncMock(return_value=None)
        mock_factory.return_value.create_source_linker.return_value = mock_linker

        response = await async_client.get(
            f"/api/v1/source-link/{uuid4()}/translated"
        )
        assert response.status_code == 200
        assert response.json() is None
