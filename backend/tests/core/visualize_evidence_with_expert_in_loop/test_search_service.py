"""Tests for evidence search service aggregation."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

_DEFAULT_TS = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _cei(**kwargs):
    """Create a SimpleNamespace for a CanonicalEvidenceItem row with defaults."""
    kwargs.setdefault("created_at", _DEFAULT_TS)
    kwargs.setdefault("updated_at", _DEFAULT_TS)
    return SimpleNamespace(**kwargs)

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

    def __iter__(self):
        """Iterate scalar rows."""
        return iter(self._values)


class _FakeResult:
    """Minimal SQLAlchemy result shim for async service tests."""

    def __init__(self, rows=None, scalars=None, scalar=None):
        self._rows = rows or []
        self._scalars = scalars or []
        self._scalar = scalar

    def all(self):
        """Return row tuples."""
        return self._rows

    def scalars(self):
        """Return scalar result wrapper."""
        return _FakeScalarResult(self._scalars)

    def scalar_one_or_none(self):
        """Return one scalar row."""
        return self._scalar

    def one_or_none(self):
        """Return one row or None (for multi-column selects)."""
        return self._rows[0] if self._rows else None

    def scalar_one(self):
        """Return one mandatory scalar row (count-style queries).

        Falls back to len(self._rows) when the caller did not pass an
        explicit `scalar=` so a count-of-rows mock yields a reasonable
        integer by default. Tests that need a different count can pass
        `scalar=N` explicitly.
        """
        if self._scalar is not None:
            return self._scalar
        return len(self._rows)


class _FakeSession:
    """Queue-backed fake async session."""

    def __init__(self, results):
        self._results = list(results)

    async def execute(self, _stmt):
        """Return the next queued result."""
        return self._results.pop(0)


@pytest.mark.asyncio
async def test_search_evidence_includes_document_title():
    """Search result rows include literature title from source metadata."""
    source_document_id = uuid4()
    evidence_id = uuid4()
    group_id = "gene=['BRCA1']"
    created_at = datetime(2026, 6, 1, tzinfo=timezone.utc)

    detail_row = _cei(
        canonical_evidence_id=evidence_id,
        source_document_id=source_document_id,
        field_id="A.gene_symbol",
        review_status="provisional",
        current_best_confidence=Decimal("0.9500"),
        active_payload={
            "group_id": group_id,
            "value": "BRCA1",
        },
        created_at=created_at,
    )
    # Pass 1 outer-SELECT row shape (after subquery): flattened scalars,
    # no longer the ORM object. Matches `page_summary` construction in
    # `SearchService.search_evidence`.
    page_row = _cei(
        group_id=group_id,
        field_count=1,
        avg_confidence=Decimal("0.9500"),
        canonical_evidence_id=evidence_id,
        source_document_id=source_document_id,
        review_status="provisional",
        created_at=created_at,
    )
    identifiers = [
        _cei(
            source_document_id=source_document_id,
            identifier_type="pmid",
            identifier_value="12345678",
        ),
    ]
    metadata = [
        _cei(
            source_document_id=source_document_id,
            raw_metadata={"title": "BRCA1 evidence paper"},
        ),
    ]

    service = SearchService(_FakeSession([
        _FakeResult(scalar=1),                    # count of groups
        _FakeResult(rows=[page_row]),             # Pass 1 page rows
        _FakeResult(rows=[detail_row]),           # Pass 2 detail rows
        _FakeResult(scalars=identifiers),         # SourceDocumentIdentifier
        _FakeResult(rows=metadata),               # SourceDocument metadata
    ]))

    response = await service.search_evidence()

    assert response.total == 1
    assert response.items[0].title == "BRCA1 evidence paper"
    assert response.items[0].pmid == "12345678"
    assert response.items[0].created_at is not None


@pytest.mark.asyncio
async def test_search_evidence_includes_created_at():
    """Search results must include created_at from canonical evidence."""
    source_document_id = uuid4()
    evidence_id = uuid4()
    group_id = "gene=['BRCA1']"
    ts = datetime(2026, 6, 10, 12, 0, 0, tzinfo=timezone.utc)

    detail_row = _cei(
        canonical_evidence_id=evidence_id,
        source_document_id=source_document_id,
        field_id="A.gene_symbol",
        review_status="provisional",
        current_best_confidence=Decimal("0.9500"),
        active_payload={
            "group_id": group_id,
            "value": "BRCA1",
        },
        created_at=ts,
    )
    page_row = _cei(
        group_id=group_id,
        field_count=1,
        avg_confidence=Decimal("0.9500"),
        canonical_evidence_id=evidence_id,
        source_document_id=source_document_id,
        review_status="provisional",
        created_at=ts,
    )

    service = SearchService(_FakeSession([
        _FakeResult(scalar=1),                    # count of groups
        _FakeResult(rows=[page_row]),             # Pass 1 page rows
        _FakeResult(rows=[detail_row]),           # Pass 2 detail rows
        _FakeResult(scalars=[]),                  # SourceDocumentIdentifier (empty)
        _FakeResult(rows=[]),                     # SourceDocument metadata (empty)
    ]))

    response = await service.search_evidence()

    assert len(response.items) > 0
    assert response.items[0].created_at == ts


@pytest.mark.asyncio
async def test_get_group_detail_pivots_distribution_and_traces():
    """Group detail pivots field rows and attaches trace highlights."""
    source_document_id = uuid4()
    gene_evidence_id = uuid4()
    disease_evidence_id = uuid4()
    group_id = "gene=['BRCA1']|variant=['c.68_69delAG']"

    rows = [
        _cei(
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
        _cei(
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
        _cei(
            source_document_id=source_document_id,
            identifier_type="pmid",
            identifier_value="12345678",
        ),
        _cei(
            source_document_id=source_document_id,
            identifier_type="doi",
            identifier_value="10.1000/example",
        ),
    ]

    service = SearchService(_FakeSession([
        _FakeResult(rows=rows),
        _FakeResult(scalars=identifiers),
        _FakeResult(rows=[({"title": "BRCA1 evidence paper"}, None, None, None, None)]),
        _FakeResult(scalar=None),  # PipelineRunState.state_json query
    ]))

    detail = await service.get_group_detail(group_id=group_id)

    assert detail.group_id == group_id
    assert detail.gene == "BRCA1"
    assert detail.disease == "Hereditary breast and ovarian cancer"
    assert detail.pmid == "12345678"
    assert detail.title == "BRCA1 evidence paper"
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
        _cei(
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
        _cei(
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
        _FakeResult(rows=[({}, None, None, None, None)]),
        _FakeResult(scalar=None),  # PipelineRunState.state_json query
    ]))

    detail = await service.get_group_detail(group_id=group_id)

    trace = next(trace for trace in detail.traces if trace.field_id == "A.gene_symbol")
    assert trace.original_value == "BRCA1"
    assert trace.translated_value == "BRCA1"
    # Verify empty metadata path: title should be None, not crash
    assert detail.title is None


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


def test_build_highlight_value_fallback_when_offsets_are_missing():
    """_build_highlight uses the evidence value when no offsets were stored."""
    highlight = _build_highlight(
        {"text_snippet": "The RB gene was evaluated.", "start_offset": None, "end_offset": None},
        value="RB",
    )

    assert highlight is not None
    assert highlight.highlight_start == 4
    assert highlight.highlight_end == 6


def test_build_highlight_value_fallback_for_two_letter_gene_symbol():
    """_build_highlight can anchor distinctive two-letter uppercase gene symbols."""
    highlight = _build_highlight(
        {"text_snippet": "Testing confirmed RB expression.", "start_offset": 500, "end_offset": 502},
        value="RB",
    )

    assert highlight is not None
    assert highlight.highlight_start == 18
    assert highlight.highlight_end == 20


def test_build_highlight_value_fallback_is_case_insensitive():
    """Value 'brca1' should highlight inside 'BRCA1 was detected.'."""
    highlight = _build_highlight(
        {"text_snippet": "BRCA1 was detected.", "start_offset": 900, "end_offset": 905},
        value="brca1",
    )

    assert highlight is not None
    assert highlight.highlight_start == 0
    assert highlight.highlight_end == 5


def test_build_highlight_value_fallback_allows_short_distinctive_tokens():
    """Short tokens with digits/punctuation can be safe enough for value fallback."""
    highlight = _build_highlight(
        {"text_snippet": "Variant V2 was observed.", "start_offset": 900, "end_offset": 902},
        value="V2",
    )

    assert highlight is not None
    assert highlight.highlight_start == 8
    assert highlight.highlight_end == 10


def test_build_highlight_value_fallback_ignores_ambiguous_single_letter_tokens():
    """Pure single-letter values should not match common prose such as articles."""
    highlight = _build_highlight(
        {"text_snippet": "A variant was detected in BRCA1.", "start_offset": 900, "end_offset": 901},
        value="A",
    )

    assert highlight is not None
    assert highlight.highlight_start == 0
    assert highlight.highlight_end == 0


def test_build_highlight_value_fallback_marks_unknown_when_value_absent():
    """When value cannot be located, highlight_start == highlight_end == 0."""
    highlight = _build_highlight(
        {"text_snippet": "No relevant finding.", "start_offset": 900, "end_offset": 910},
        value="BRCA1",
    )

    assert highlight is not None
    assert highlight.highlight_start == highlight.highlight_end == 0


def test_build_highlight_returns_none_for_empty_text():
    """_build_highlight returns None when text_snippet is empty."""
    assert _build_highlight({"text_snippet": ""}) is None
    assert _build_highlight({"text_snippet": None}) is None


def test_build_highlight_returns_none_for_string_source():
    """_build_highlight returns None when source_span is a string, not a dict.

    Benchmark/ground-truth imports store ``source`` as a plain string
    (e.g. ``"benchmark_ground_truth"``) instead of the usual dict with
    ``text_snippet`` / offsets.  The function must not crash.
    """
    assert _build_highlight("benchmark_ground_truth") is None
    assert _build_highlight("preprocessed") is None


@pytest.mark.asyncio
async def test_get_group_detail_handles_string_source_field():
    """Group detail does not crash when active_payload['source'] is a string.

    Ground-truth evidence stores source as a plain string rather than a dict.
    """
    source_document_id = uuid4()
    ev_id = uuid4()
    group_id = "gene=['BRCA1']"

    rows = [
        _cei(
            canonical_evidence_id=ev_id,
            source_document_id=source_document_id,
            field_id="A.gene_symbol",
            review_status="approved",
            current_best_confidence=Decimal("1.0000"),
            active_payload={
                "group_id": group_id,
                "field_name": "Gene symbol",
                "category": "A",
                "value": "BRCA1",
                "track": "original",
                "source": "benchmark_ground_truth",
            },
        ),
    ]

    service = SearchService(_FakeSession([
        _FakeResult(rows=rows),
        _FakeResult(scalars=[]),
        _FakeResult(rows=[({}, None, None, None, None)]),
        _FakeResult(scalar=None),
    ]))

    detail = await service.get_group_detail(group_id=group_id)

    assert len(detail.items) == 1
    assert detail.items[0].value == "BRCA1"
    # String source should produce a trace with no highlight (original=None)
    assert len(detail.traces) == 1
    assert detail.traces[0].original is None


@pytest.mark.asyncio
async def test_get_group_detail_skips_field_ids_without_standard_tracks():
    """Field IDs with only non-standard tracks should be skipped in traces."""
    source_document_id = uuid4()
    ev_id = uuid4()
    group_id = "gene=['BRCA1']"

    rows = [
        _cei(
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
        _FakeResult(rows=[({}, None, None, None, None)]),
        _FakeResult(scalar=None),  # PipelineRunState.state_json query
    ]))

    detail = await service.get_group_detail(group_id=group_id)

    # The 'review' track row should be in items but NOT produce a trace
    assert len(detail.items) == 1
    assert len(detail.traces) == 0
    assert detail.title is None


@pytest.mark.asyncio
async def test_get_group_detail_single_track_field_produces_partial_trace():
    """A field ID with only an 'original' row should produce a trace with translated=None."""
    source_document_id = uuid4()
    ev_id = uuid4()
    group_id = "gene=['BRCA1']"

    rows = [
        _cei(
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
        _FakeResult(rows=[({}, None, None, None, None)]),
        _FakeResult(scalar=None),  # PipelineRunState.state_json query
    ]))

    detail = await service.get_group_detail(group_id=group_id)

    assert len(detail.traces) == 1
    assert detail.traces[0].original is not None
    assert detail.traces[0].translated is None
    assert detail.title is None


@pytest.mark.asyncio
async def test_get_group_detail_falls_back_to_reconciled_track():
    """When original/translated have string sources, reconciled row provides text.

    Ground-truth imports store ``source`` as a plain string on the translated
    track but have a dict source with ``text_snippet`` on the reconciled track.
    The trace should fall back to the reconciled row's highlight.
    """
    source_document_id = uuid4()
    translated_id = uuid4()
    reconciled_id = uuid4()
    group_id = "gene=['BRCA1']"

    rows = [
        _cei(
            canonical_evidence_id=translated_id,
            source_document_id=source_document_id,
            field_id="A.gene_symbol",
            review_status="approved",
            current_best_confidence=Decimal("1.0"),
            active_payload={
                "group_id": group_id,
                "field_name": "Gene symbol",
                "category": "A",
                "value": "BRCA1",
                "track": "translated",
                "source": "benchmark_ground_truth",
            },
        ),
        _cei(
            canonical_evidence_id=reconciled_id,
            source_document_id=source_document_id,
            field_id="A.gene_symbol",
            review_status="approved",
            current_best_confidence=Decimal("1.0"),
            active_payload={
                "group_id": group_id,
                "field_name": "Gene symbol",
                "category": "A",
                "value": "BRCA1",
                "track": "reconciled",
                "source": {
                    "text_snippet": "BRCA1 was detected in the proband.",
                    "start_offset": 0,
                    "end_offset": 5,
                    "page": 1,
                },
            },
        ),
    ]

    service = SearchService(_FakeSession([
        _FakeResult(rows=rows),
        _FakeResult(scalars=[]),
        _FakeResult(rows=[({}, None, None, None, None)]),
        _FakeResult(scalar=None),
    ]))

    detail = await service.get_group_detail(group_id=group_id)

    assert len(detail.traces) == 1
    trace = detail.traces[0]
    # Reconciled row's highlight should be used as fallback
    assert trace.original is not None
    assert trace.original.text == "BRCA1 was detected in the proband."
