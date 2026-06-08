"""Tests for evidence search service aggregation."""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.core.visualize_evidence_with_expert_in_loop.search_service import (
    SearchService,
    _build_highlight,
    _coerce_str,
)


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
                "source": {
                    "text_snippet": "BRCA1 was detected in the proband.",
                    "start_offset": 0,
                    "end_offset": 5,
                    "page": 1,
                },
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
                "source": {
                    "text_snippet": "诊断为遗传性乳腺卵巢癌。",
                    "start_offset": 3,
                    "end_offset": 13,
                    "page": 2,
                },
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

    service = SearchService(_FakeSession([
        _FakeResult(rows=rows),
        _FakeResult(scalars=identifiers),
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


@pytest.mark.asyncio
async def test_get_group_detail_includes_value_anchors_for_paired_field():
    """Paired original/translated rows expose both value anchors on one trace."""
    source_document_id = uuid4()
    original_id = uuid4()
    translated_id = uuid4()
    group_id = "gene=['BRCA1']"

    rows = [
        SimpleNamespace(
            canonical_evidence_id=original_id,
            source_document_id=source_document_id,
            field_id="A.gene_symbol",
            review_status="provisional",
            current_best_confidence=Decimal("0.9500"),
            active_payload={
                "group_id": group_id,
                "field_name": "Gene symbol",
                "category": "A",
                "value": "BRCA1",
                "track": "original",
                "source": {
                    "text_snippet": "BRCA1 was detected in the proband.",
                    "start_offset": 0,
                    "end_offset": 5,
                    "page": 1,
                },
            },
        ),
        SimpleNamespace(
            canonical_evidence_id=translated_id,
            source_document_id=source_document_id,
            field_id="A.gene_symbol",
            review_status="provisional",
            current_best_confidence=Decimal("0.9300"),
            active_payload={
                "group_id": group_id,
                "field_name": "Gene symbol",
                "category": "A",
                "value": "BRCA1",
                "track": "translated",
                "source": {
                    "text_snippet": "在先证者中检测到 BRCA1。",
                    "start_offset": 7,
                    "end_offset": 12,
                    "page": 1,
                },
            },
        ),
    ]

    service = SearchService(_FakeSession([
        _FakeResult(rows=rows),
        _FakeResult(scalars=[]),
    ]))

    detail = await service.get_group_detail(group_id=group_id)

    trace = next(trace for trace in detail.traces if trace.field_id == "A.gene_symbol")
    assert trace.original_value == "BRCA1"
    assert trace.translated_value == "BRCA1"


def test_coerce_str_joins_list_values():
    """_coerce_str joins list values with comma separator."""
    assert _coerce_str(["BRCA1", "BRCA2"]) == "BRCA1, BRCA2"


def test_build_highlight_clamps_invalid_offsets():
    """_build_highlight clamps end_offset that exceeds text length."""
    highlight = _build_highlight({
        "text_snippet": "BRCA1 was detected.",
        "start_offset": 0,
        "end_offset": 200,
        "page": 3,
    })

    assert highlight is not None
    assert highlight.highlight_end == len("BRCA1 was detected.")
    assert highlight.page == 3


def test_build_highlight_value_fallback_for_document_global_offsets():
    """_build_highlight falls back to value-based search when offsets exceed snippet."""
    highlight = _build_highlight(
        {"text_snippet": "BRCA1 was detected in the proband.", "start_offset": 500, "end_offset": 505},
        value="BRCA1",
    )
    assert highlight is not None
    assert highlight.highlight_start == 0
    assert highlight.highlight_end == 5


def test_build_highlight_value_fallback_requires_min_length():
    """_build_highlight skips value fallback for short values (< 3 chars)."""
    highlight = _build_highlight(
        {"text_snippet": "A was detected.", "start_offset": 500, "end_offset": 501},
        value="A",
    )
    # Short value should NOT be used as substring fallback — offsets go to (0, 0)
    assert highlight is not None
    assert highlight.highlight_start == 0
    assert highlight.highlight_end == 0


def test_build_highlight_returns_none_for_empty_text():
    """_build_highlight returns None when text_snippet is empty."""
    assert _build_highlight({"text_snippet": ""}) is None
    assert _build_highlight({"text_snippet": None}) is None


@pytest.mark.asyncio
async def test_get_group_detail_skips_field_ids_without_standard_tracks():
    """Field IDs with only non-standard tracks should be skipped in traces."""
    source_document_id = uuid4()
    ev_id = uuid4()
    group_id = "gene=['BRCA1']"

    rows = [
        SimpleNamespace(
            canonical_evidence_id=ev_id,
            source_document_id=source_document_id,
            field_id="A.gene_symbol",
            review_status="provisional",
            current_best_confidence=Decimal("0.9"),
            active_payload={
                "group_id": group_id,
                "field_name": "Gene symbol",
                "category": "A",
                "value": "BRCA1",
                "track": "review",
                "source": {"text_snippet": "BRCA1 gene.", "start_offset": 0, "end_offset": 5},
            },
        ),
    ]
    identifiers: list = []

    service = SearchService(_FakeSession([
        _FakeResult(rows=rows),
        _FakeResult(scalars=identifiers),
    ]))

    detail = await service.get_group_detail(group_id=group_id)

    # The 'review' track row should be in items but NOT produce a trace
    assert len(detail.items) == 1
    assert len(detail.traces) == 0


@pytest.mark.asyncio
async def test_get_group_detail_single_track_field_produces_partial_trace():
    """A field ID with only an 'original' row should produce a trace with translated=None."""
    source_document_id = uuid4()
    ev_id = uuid4()
    group_id = "gene=['BRCA1']"

    rows = [
        SimpleNamespace(
            canonical_evidence_id=ev_id,
            source_document_id=source_document_id,
            field_id="A.gene_symbol",
            review_status="provisional",
            current_best_confidence=Decimal("0.9"),
            active_payload={
                "group_id": group_id,
                "field_name": "Gene symbol",
                "category": "A",
                "value": "BRCA1",
                "track": "original",
                "source": {"text_snippet": "BRCA1 gene.", "start_offset": 0, "end_offset": 5},
            },
        ),
    ]
    identifiers: list = []

    service = SearchService(_FakeSession([
        _FakeResult(rows=rows),
        _FakeResult(scalars=identifiers),
    ]))

    detail = await service.get_group_detail(group_id=group_id)

    assert len(detail.traces) == 1
    assert detail.traces[0].original is not None
    assert detail.traces[0].translated is None
