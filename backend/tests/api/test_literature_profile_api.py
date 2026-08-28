"""Tests for literature profile API routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from src.dao.postgresql.contracts import (
    LiteratureProfileRow,
    LiteratureProfileSearchItem,
)


@pytest.mark.asyncio
async def test_search_literature_returns_literature_profiles(async_client: AsyncClient):
    """GET /api/v1/evidence/literature/search returns paginated results."""
    doc_id = uuid4()
    profile_id = uuid4()
    mock_items = [
        LiteratureProfileSearchItem(
            literature_profile_id=str(profile_id),
            source_document_id=str(doc_id),
            pmid="12345678",
            doi="10.1234/test",
            title="Test Article",
            journal="Test Journal",
            publication_year=2024,
            review_status="provisional",
            overall_confidence=0.85,
            total_evidence_fields=5,
            found_count=4,
            evidence_group_count=2,
            gene="BRCA1",
            variant="c.68_69delAG",
            disease="Breast cancer",
            classification="Pathogenic",
            created_at=None,
        )
    ]

    with patch(
        "src.dao.postgresql.literature_profile_repo.LiteratureProfileRepository.search",
        new_callable=AsyncMock,
        return_value=(mock_items, 1),
    ):
        response = await async_client.get(
            "/api/v1/evidence/literature/search",
            params={"gene": "BRCA1", "page": 1, "page_size": 50},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["page"] == 1
    assert data["page_size"] == 50
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["literature_profile_id"] == str(profile_id)
    assert item["pmid"] == "12345678"
    assert item["gene"] == "BRCA1"


@pytest.mark.asyncio
async def test_get_literature_detail_returns_profile_with_groups(async_client: AsyncClient):
    """GET /api/v1/evidence/literature/{id}/detail returns full profile."""
    doc_id = uuid4()
    profile_id = uuid4()
    evidence_id = uuid4()
    mock_profile = LiteratureProfileRow(
        literature_profile_id=str(profile_id),
        source_document_id=str(doc_id),
        pmid="12345678",
        doi="10.1234/test",
        title="Test Article",
        authors=["Author A", "Author B"],
        journal="Test Journal",
        publication_year=2024,
        evidence_groups=[
            {
                "group_id": "gene=['BRCA1']|variant=['c.68_69delAG']",
                "summary": {"gene": "BRCA1", "variant": "c.68_69delAG"},
                "avg_confidence": 0.9,
                "field_count": 3,
                "review_status": "provisional",
                "fields": [
                    {
                        "canonical_evidence_id": str(evidence_id),
                        "field_id": "A.gene_symbol",
                        "field_name": "Gene Symbol",
                        "category": "A",
                        "value": "BRCA1",
                        "confidence": 0.95,
                        "status": "found",
                        "track": "original",
                    }
                ],
            }
        ],
        review_status="provisional",
        review_notes=None,
        overall_confidence=0.88,
        total_evidence_fields=5,
        found_count=4,
        not_found_count=1,
        created_at=None,
        updated_at=None,
    )

    with patch(
        "src.dao.postgresql.literature_profile_repo.LiteratureProfileRepository.get_by_document",
        new_callable=AsyncMock,
        return_value=mock_profile,
    ):
        response = await async_client.get(
            f"/api/v1/evidence/literature/{doc_id}/detail",
        )

    assert response.status_code == 200
    data = response.json()
    assert data["literature_profile_id"] == str(profile_id)
    assert data["source_document_id"] == str(doc_id)
    assert data["pmid"] == "12345678"
    assert data["title"] == "Test Article"
    assert data["authors"] == ["Author A", "Author B"]
    assert len(data["evidence_groups"]) == 1
    group = data["evidence_groups"][0]
    assert group["group_id"] == "gene=['BRCA1']|variant=['c.68_69delAG']"
    assert len(group["fields"]) == 1
    assert data["total_evidence_fields"] == 5
    assert data["found_count"] == 4
    assert data["not_found_count"] == 1


@pytest.mark.asyncio
async def test_get_literature_detail_404(async_client: AsyncClient):
    """GET /api/v1/evidence/literature/{id}/detail returns 404 when missing."""
    with patch(
        "src.dao.postgresql.literature_profile_repo.LiteratureProfileRepository.get_by_document",
        new_callable=AsyncMock,
        return_value=None,
    ):
        response = await async_client.get(
            f"/api/v1/evidence/literature/{uuid4()}/detail",
        )

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["message"] == "Literature profile not found"
