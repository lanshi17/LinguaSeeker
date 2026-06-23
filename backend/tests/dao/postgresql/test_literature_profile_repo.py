"""Tests for LiteratureProfileRepository."""
from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


def _fake_session() -> MagicMock:
    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


# ── _build_evidence_groups tests ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_build_evidence_groups_groups_by_group_id() -> None:
    """_build_evidence_groups groups rows by active_payload['group_id']."""
    from src.dao.postgresql.literature_profile_repo import LiteratureProfileRepository

    repo = LiteratureProfileRepository(MagicMock())
    rows = [
        {
            "canonical_evidence_id": str(uuid4()),
            "field_id": "A.gene_symbol",
            "review_status": "provisional",
            "current_best_confidence": 0.95,
            "active_payload": {
                "group_id": "chain_001",
                "field_id": "A.gene_symbol",
                "field_name": "Gene Symbol",
                "category": "A",
                "value": "BRCA1",
                "confidence": 0.95,
                "status": "found",
                "track": "original",
            },
        },
        {
            "canonical_evidence_id": str(uuid4()),
            "field_id": "A.variant_hgvs_c",
            "review_status": "provisional",
            "current_best_confidence": 0.90,
            "active_payload": {
                "group_id": "chain_001",
                "field_id": "A.variant_hgvs_c",
                "field_name": "HGVS c.",
                "category": "A",
                "value": "c.5266dupC",
                "confidence": 0.90,
                "status": "found",
                "track": "original",
            },
        },
    ]
    groups = repo._build_evidence_groups(rows)
    assert len(groups) == 1
    assert groups[0]["group_id"] == "chain_001"
    assert groups[0]["summary"]["gene"] == "BRCA1"
    assert groups[0]["summary"]["variant"] == "c.5266dupC"
    assert groups[0]["field_count"] == 2


@pytest.mark.asyncio
async def test_build_evidence_groups_skips_rows_without_group_id() -> None:
    """Rows with empty group_id are excluded."""
    from src.dao.postgresql.literature_profile_repo import LiteratureProfileRepository

    repo = LiteratureProfileRepository(MagicMock())
    rows = [
        {
            "canonical_evidence_id": str(uuid4()),
            "field_id": "A.gene_symbol",
            "review_status": "provisional",
            "current_best_confidence": 0.95,
            "active_payload": {
                "group_id": "",
                "field_id": "A.gene_symbol",
                "value": "BRCA1",
            },
        },
    ]
    groups = repo._build_evidence_groups(rows)
    assert len(groups) == 0


@pytest.mark.asyncio
async def test_build_evidence_groups_review_status_worst_case() -> None:
    """Review status uses worst-case semantics."""
    from src.dao.postgresql.literature_profile_repo import LiteratureProfileRepository

    repo = LiteratureProfileRepository(MagicMock())
    rows = [
        {
            "canonical_evidence_id": str(uuid4()),
            "field_id": "A.gene_symbol",
            "review_status": "approved",
            "current_best_confidence": 0.95,
            "active_payload": {
                "group_id": "chain_001",
                "field_id": "A.gene_symbol",
                "value": "BRCA1",
            },
        },
        {
            "canonical_evidence_id": str(uuid4()),
            "field_id": "A.variant_hgvs_c",
            "review_status": "rejected",
            "current_best_confidence": 0.90,
            "active_payload": {
                "group_id": "chain_001",
                "field_id": "A.variant_hgvs_c",
                "value": "c.5266dupC",
            },
        },
    ]
    groups = repo._build_evidence_groups(rows)
    assert groups[0]["review_status"] == "rejected"


@pytest.mark.asyncio
async def test_build_evidence_groups_multiple_groups() -> None:
    """Multiple distinct group_ids produce separate groups."""
    from src.dao.postgresql.literature_profile_repo import LiteratureProfileRepository

    repo = LiteratureProfileRepository(MagicMock())
    rows = [
        {
            "canonical_evidence_id": str(uuid4()),
            "field_id": "A.gene_symbol",
            "review_status": "provisional",
            "current_best_confidence": 0.95,
            "active_payload": {
                "group_id": "chain_001",
                "field_id": "A.gene_symbol",
                "value": "BRCA1",
            },
        },
        {
            "canonical_evidence_id": str(uuid4()),
            "field_id": "A.gene_symbol",
            "review_status": "provisional",
            "current_best_confidence": 0.88,
            "active_payload": {
                "group_id": "chain_002",
                "field_id": "A.gene_symbol",
                "value": "TP53",
            },
        },
    ]
    groups = repo._build_evidence_groups(rows)
    assert len(groups) == 2
    group_ids = {g["group_id"] for g in groups}
    assert group_ids == {"chain_001", "chain_002"}


@pytest.mark.asyncio
async def test_build_evidence_groups_avg_confidence() -> None:
    """avg_confidence is the mean of current_best_confidence values."""
    from src.dao.postgresql.literature_profile_repo import LiteratureProfileRepository

    repo = LiteratureProfileRepository(MagicMock())
    rows = [
        {
            "canonical_evidence_id": str(uuid4()),
            "field_id": "A.gene_symbol",
            "review_status": "provisional",
            "current_best_confidence": 0.80,
            "active_payload": {
                "group_id": "chain_001",
                "field_id": "A.gene_symbol",
                "value": "BRCA1",
            },
        },
        {
            "canonical_evidence_id": str(uuid4()),
            "field_id": "A.variant_hgvs_c",
            "review_status": "provisional",
            "current_best_confidence": 0.60,
            "active_payload": {
                "group_id": "chain_001",
                "field_id": "A.variant_hgvs_c",
                "value": "c.5266dupC",
            },
        },
    ]
    groups = repo._build_evidence_groups(rows)
    assert groups[0]["avg_confidence"] == pytest.approx(0.70)


@pytest.mark.asyncio
async def test_build_evidence_groups_summary_first_match_wins() -> None:
    """Summary extraction uses first-match-wins semantics."""
    from src.dao.postgresql.literature_profile_repo import LiteratureProfileRepository

    repo = LiteratureProfileRepository(MagicMock())
    rows = [
        {
            "canonical_evidence_id": str(uuid4()),
            "field_id": "A.gene_symbol",
            "review_status": "provisional",
            "current_best_confidence": 0.95,
            "active_payload": {
                "group_id": "chain_001",
                "field_id": "A.gene_symbol",
                "value": "BRCA1",
            },
        },
        {
            "canonical_evidence_id": str(uuid4()),
            "field_id": "A.gene_aliases",
            "review_status": "provisional",
            "current_best_confidence": 0.90,
            "active_payload": {
                "group_id": "chain_001",
                "field_id": "A.gene_aliases",
                "value": "FANCS",
            },
        },
    ]
    groups = repo._build_evidence_groups(rows)
    # gene should stay as BRCA1, not be overwritten
    assert groups[0]["summary"]["gene"] == "BRCA1"


@pytest.mark.asyncio
async def test_build_evidence_groups_disease_and_classification() -> None:
    """Summary includes disease and classification from appropriate fields."""
    from src.dao.postgresql.literature_profile_repo import LiteratureProfileRepository

    repo = LiteratureProfileRepository(MagicMock())
    rows = [
        {
            "canonical_evidence_id": str(uuid4()),
            "field_id": "B.disease_diagnosis",
            "review_status": "provisional",
            "current_best_confidence": 0.85,
            "active_payload": {
                "group_id": "chain_001",
                "field_id": "B.disease_diagnosis",
                "value": "Breast cancer",
            },
        },
        {
            "canonical_evidence_id": str(uuid4()),
            "field_id": "J.authority_classification",
            "review_status": "provisional",
            "current_best_confidence": 0.92,
            "active_payload": {
                "group_id": "chain_001",
                "field_id": "J.authority_classification",
                "value": "Pathogenic",
            },
        },
    ]
    groups = repo._build_evidence_groups(rows)
    assert groups[0]["summary"]["disease"] == "Breast cancer"
    assert groups[0]["summary"]["classification"] == "Pathogenic"


@pytest.mark.asyncio
async def test_build_evidence_groups_empty_input() -> None:
    """Empty input returns empty list."""
    from src.dao.postgresql.literature_profile_repo import LiteratureProfileRepository

    repo = LiteratureProfileRepository(MagicMock())
    groups = repo._build_evidence_groups([])
    assert groups == []


@pytest.mark.asyncio
async def test_build_evidence_groups_fields_contain_required_keys() -> None:
    """Each field entry in a group contains the expected keys."""
    from src.dao.postgresql.literature_profile_repo import LiteratureProfileRepository

    repo = LiteratureProfileRepository(MagicMock())
    rows = [
        {
            "canonical_evidence_id": str(uuid4()),
            "field_id": "A.gene_symbol",
            "review_status": "provisional",
            "current_best_confidence": 0.95,
            "active_payload": {
                "group_id": "chain_001",
                "field_id": "A.gene_symbol",
                "field_name": "Gene Symbol",
                "category": "A",
                "value": "BRCA1",
                "confidence": 0.95,
                "status": "found",
                "track": "original",
            },
        },
    ]
    groups = repo._build_evidence_groups(rows)
    field = groups[0]["fields"][0]
    assert field["canonical_evidence_id"] is not None
    assert field["field_id"] == "A.gene_symbol"
    assert field["value"] == "BRCA1"
    assert field["confidence"] == 0.95
    assert field["status"] == "found"
    assert field["track"] == "original"


@pytest.mark.asyncio
async def test_build_evidence_groups_field_confidence_is_json_serializable() -> None:
    """Field confidence must not leak Decimal values into JSONB payloads."""
    from src.dao.postgresql.literature_profile_repo import LiteratureProfileRepository

    repo = LiteratureProfileRepository(MagicMock())
    rows = [
        {
            "canonical_evidence_id": str(uuid4()),
            "field_id": "B.disease_diagnosis",
            "review_status": "provisional",
            "current_best_confidence": Decimal("0.91"),
            "active_payload": {
                "group_id": "chain_001",
                "field_id": "B.disease_diagnosis",
                "value": "Fabry disease",
            },
        },
    ]

    groups = repo._build_evidence_groups(rows)

    assert groups[0]["fields"][0]["confidence"] == 0.91
    json.dumps(groups)


# ── get_by_document tests ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_by_document_returns_profile_dict() -> None:
    """get_by_document returns a dict with the expected keys when a row exists."""
    from datetime import datetime

    from src.dao.postgresql.literature_profile_repo import LiteratureProfileRepository

    profile_id = uuid4()
    doc_id = uuid4()

    fake_row = MagicMock()
    fake_row.literature_profile_id = profile_id
    fake_row.source_document_id = doc_id
    fake_row.pmid = "12345678"
    fake_row.doi = "10.1234/test"
    fake_row.title = "Test Title"
    fake_row.authors = ["Author A"]
    fake_row.journal = "Test Journal"
    fake_row.publication_year = 2024
    fake_row.evidence_groups = [{"group_id": "g1", "fields": []}]
    fake_row.review_status = "provisional"
    fake_row.review_notes = None
    fake_row.overall_confidence = 0.95
    fake_row.total_evidence_fields = 10
    fake_row.found_count = 8
    fake_row.not_found_count = 2
    fake_row.created_at = now
    fake_row.updated_at = now

    session = _fake_session()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = fake_row
    session.execute.return_value = mock_result

    repo = LiteratureProfileRepository(session)
    result = await repo.get_by_document(doc_id)

    assert result is not None
    expected_keys = {
        "literature_profile_id",
        "source_document_id",
        "pmid",
        "doi",
        "title",
        "evidence_groups",
        "review_status",
        "overall_confidence",
        "total_evidence_fields",
        "found_count",
        "not_found_count",
    }
    assert expected_keys.issubset(result.keys())
    assert result["literature_profile_id"] == str(profile_id)
    assert result["source_document_id"] == str(doc_id)
    assert result["pmid"] == "12345678"
    assert result["doi"] == "10.1234/test"
    assert result["title"] == "Test Title"
    assert result["overall_confidence"] == pytest.approx(0.95)
    assert result["total_evidence_fields"] == 10
    assert result["found_count"] == 8
    assert result["not_found_count"] == 2


@pytest.mark.asyncio
async def test_get_by_document_returns_none_when_not_found() -> None:
    """get_by_document returns None when no matching row exists."""
    from src.dao.postgresql.literature_profile_repo import LiteratureProfileRepository

    session = _fake_session()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result

    repo = LiteratureProfileRepository(session)
    result = await repo.get_by_document(uuid4())

    assert result is None


# ── search tests ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_returns_items_and_total() -> None:
    """search returns (items, total_count) with expected dict keys."""
    from datetime import datetime

    from src.dao.postgresql.literature_profile_repo import LiteratureProfileRepository

    profile_id = uuid4()
    doc_id = uuid4()
    now = datetime.now()

    fake_row = MagicMock()
    fake_row.literature_profile_id = profile_id
    fake_row.source_document_id = doc_id
    fake_row.pmid = "12345678"
    fake_row.doi = "10.1234/test"
    fake_row.title = "Test Title"
    fake_row.journal = "Test Journal"
    fake_row.publication_year = 2024
    fake_row.review_status = "provisional"
    fake_row.overall_confidence = 0.90
    fake_row.total_evidence_fields = 5
    fake_row.found_count = 4
    fake_row.evidence_groups = [
        {
            "group_id": "g1",
            "summary": {
                "gene": "BRCA1",
                "variant": "c.5266dupC",
                "disease": "Breast cancer",
                "classification": "Pathogenic",
            },
            "fields": [],
        }
    ]

    session = _fake_session()

    # First execute call: count query
    count_result = MagicMock()
    count_result.scalar_one.return_value = 1

    # Second execute call: data query
    data_result = MagicMock()
    data_result.scalars.return_value.all.return_value = [fake_row]

    session.execute = AsyncMock(side_effect=[count_result, data_result])

    repo = LiteratureProfileRepository(session)
    items, total = await repo.search(page=1, page_size=50)

    assert total == 1
    assert len(items) == 1

    item = items[0]
    expected_keys = {
        "literature_profile_id",
        "source_document_id",
        "pmid",
        "doi",
        "title",
        "review_status",
        "overall_confidence",
        "total_evidence_fields",
        "found_count",
        "evidence_group_count",
        "gene",
        "variant",
        "disease",
        "classification",
    }
    assert expected_keys.issubset(item.keys())
    assert item["literature_profile_id"] == str(profile_id)
    assert item["gene"] == "BRCA1"
    assert item["variant"] == "c.5266dupC"
    assert item["disease"] == "Breast cancer"
    assert item["classification"] == "Pathogenic"
    assert item["evidence_group_count"] == 1
