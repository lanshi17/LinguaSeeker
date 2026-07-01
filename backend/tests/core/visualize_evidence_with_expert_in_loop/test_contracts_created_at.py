"""Tests for created_at field exposure in evidence contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    EvidenceSearchResult,
    LiteratureProfileSummary,
)


def test_evidence_search_result_has_created_at():
    """EvidenceSearchResult must accept and expose a created_at field."""
    now = datetime(2026, 6, 10, 12, 0, 0, tzinfo=timezone.utc)
    result = EvidenceSearchResult(
        group_id="g1",
        source_document_id=uuid4(),
        created_at=now,
    )
    assert result.created_at == now


def test_evidence_search_result_created_at_optional():
    """created_at should be optional (backward compatible)."""
    result = EvidenceSearchResult(
        group_id="g1",
        source_document_id=uuid4(),
    )
    assert result.created_at is None


def test_literature_profile_summary_has_created_at():
    """LiteratureProfileSummary must accept and expose a created_at field."""
    now = datetime(2026, 6, 10, 12, 0, 0, tzinfo=timezone.utc)
    summary = LiteratureProfileSummary(
        literature_profile_id=uuid4(),
        source_document_id=uuid4(),
        created_at=now,
    )
    assert summary.created_at == now


def test_literature_profile_summary_created_at_optional():
    """created_at should be optional (backward compatible)."""
    summary = LiteratureProfileSummary(
        literature_profile_id=uuid4(),
        source_document_id=uuid4(),
    )
    assert summary.created_at is None
