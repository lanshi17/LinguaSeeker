"""Tests for evidence search service aggregation."""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.core.visualize_evidence_with_expert_in_loop.search_service import SearchService


class _FakeScalarResult:
    """Minimal scalar result shim for async service tests."""

    def __init__(self, values):
        self._values = values

    def all(self):
        """Return scalar rows."""
        return self._values


class _FakeResult:
    """Minimal SQLAlchemy result shim for async service tests."""

    def __init__(self, rows=None, scalars=None):
        self._rows = rows or []
        self._scalars = scalars or []

    def all(self):
        """Return row tuples."""
        return self._rows

    def scalars(self):
        """Return scalar result wrapper."""
        return _FakeScalarResult(self._scalars)


class _FakeSession:
    """Queue-backed fake async session."""

    def __init__(self, results):
        self._results = list(results)

    async def execute(self, _stmt):
        """Return the next queued result."""
        return self._results.pop(0)


@pytest.mark.asyncio
async def test_get_group_detail_pivots_distribution_and_traces():
    """Group detail pivots field rows and attaches trace highlights."""
    source_document_id = uuid4()
    gene_evidence_id = uuid4()
    disease_evidence_id = uuid4()
    group_id = "gene=['BRCA1']|variant=['c.68_69delAG']"

    rows = [
        SimpleNamespace(
            canonical_evidence_id=gene_evidence_id,
            source_document_id=source_document_id,
            field_id="A.gene_symbol",
            review_status="provisional",
            current_best_confidence=Decimal("0.9500"),
            active_payload={
                "group_id": group_id,
                "field_name": "Gene symbol",
                "category": "A",
                "value": ["BRCA1"],
                "track": "original",
            },
        ),
        SimpleNamespace(
            canonical_evidence_id=disease_evidence_id,
            source_document_id=source_document_id,
            field_id="B.disease_diagnosis",
            review_status="approved",
            current_best_confidence=Decimal("0.9000"),
            active_payload={
                "group_id": group_id,
                "field_name": "Disease diagnosis",
                "category": "B",
                "value": "Hereditary breast and ovarian cancer",
                "track": "translated",
            },
        ),
    ]
    identifiers = [
        SimpleNamespace(
            source_document_id=source_document_id,
            identifier_type="pmid",
            identifier_value="12345678",
        ),
        SimpleNamespace(
            source_document_id=source_document_id,
            identifier_type="doi",
            identifier_value="10.1000/example",
        ),
    ]
    run_items = [
        SimpleNamespace(
            canonical_evidence_id=gene_evidence_id,
            field_id="A.gene_symbol",
            track="original",
            source_span={
                "text_snippet": "BRCA1 was detected in the proband.",
                "start_offset": 0,
                "end_offset": 5,
                "page": 1,
            },
        ),
        SimpleNamespace(
            canonical_evidence_id=disease_evidence_id,
            field_id="B.disease_diagnosis",
            track="translated",
            source_span={
                "text_snippet": "诊断为遗传性乳腺卵巢癌。",
                "start_offset": 3,
                "end_offset": 13,
                "page": 2,
            },
        ),
    ]

    service = SearchService(_FakeSession([
        _FakeResult(rows=rows),
        _FakeResult(scalars=identifiers),
        _FakeResult(scalars=run_items),
    ]))

    detail = await service.get_group_detail(group_id=group_id)

    assert detail.group_id == group_id
    assert detail.gene == "BRCA1"
    assert detail.disease == "Hereditary breast and ovarian cancer"
    assert detail.pmid == "12345678"
    assert detail.distribution.by_category == {"A": 1, "B": 1}
    assert detail.distribution.by_status == {"provisional": 1, "approved": 1}
    assert detail.item_count == 2
    assert detail.traces[0].original is not None
    assert detail.traces[1].translated is not None
