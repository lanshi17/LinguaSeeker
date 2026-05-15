import pytest
from pydantic import ValidationError

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceItem,
    EvidenceStatus,
    ExternalIds,
    PageSpan,
    SourceLocation,
    SourcePrecision,
    Track,
    TrackDocument,
)


def test_track_document_accepts_upstream_spans():
    doc = TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text="Patient 1 has BRCA1 c.68_69delAG.",
        page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=36)],
        external_ids=ExternalIds(pmid="123"),
    )

    assert doc.track == Track.ORIGINAL
    assert doc.page_spans[0].span_id == "p1"


def test_evidence_item_found_requires_confidence_in_range():
    source = SourceLocation(
        span_id="p1",
        page=1,
        start_offset=14,
        end_offset=19,
        context_type="text",
        context_ref="Results paragraph 1",
        text_snippet="BRCA1",
        source_precision=SourcePrecision.EXACT,
    )

    item = EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.FOUND,
        value="BRCA1",
        acmg_codes=[],
        clingen_modules=["variant_evidence"],
        source=source,
        confidence=0.95,
    )

    assert item.source == source


def test_evidence_item_rejects_invalid_confidence():
    with pytest.raises(ValidationError):
        EvidenceItem(
            field_id="A.gene_symbol",
            category="A",
            field_name="Gene symbol",
            status=EvidenceStatus.FOUND,
            value="BRCA1",
            acmg_codes=[],
            clingen_modules=[],
            confidence=1.5,
        )
