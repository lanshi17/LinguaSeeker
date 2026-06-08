"""Tests for LiteratureProfileRepository."""
from __future__ import annotations

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
