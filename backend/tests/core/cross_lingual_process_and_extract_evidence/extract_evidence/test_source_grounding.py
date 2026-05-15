from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceItem,
    EvidenceStatus,
    PageSpan,
    SourceLocation,
    SourcePrecision,
    Track,
    TrackDocument,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.core import SourceGrounder


def _doc() -> TrackDocument:
    text = "Page one BRCA1 evidence.\n\nPage two has c.68_69delAG evidence."
    return TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text=text,
        page_spans=[
            PageSpan(span_id="p1", page=1, start_offset=0, end_offset=24),
            PageSpan(span_id="p2", page=2, start_offset=26, end_offset=len(text)),
        ],
    )


def test_source_grounding_keeps_exact_source():
    item = EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.FOUND,
        value="BRCA1",
        source=SourceLocation(
            span_id="p1",
            page=1,
            start_offset=9,
            end_offset=14,
            context_type="text",
            context_ref="Results",
            text_snippet="BRCA1",
            source_precision=SourcePrecision.EXACT,
        ),
        confidence=0.9,
    )

    grounded = SourceGrounder().ground_items(_doc(), [item])

    assert grounded[0].source.source_precision == SourcePrecision.EXACT
    assert grounded[0].raw_source is None


def test_source_grounding_corrects_wrong_offset():
    item = EvidenceItem(
        field_id="A.variant_hgvs_c",
        category="A",
        field_name="HGVS cDNA",
        status=EvidenceStatus.FOUND,
        value="c.68_69delAG",
        source=SourceLocation(
            span_id="p1",
            page=1,
            start_offset=0,
            end_offset=12,
            context_type="text",
            context_ref="Table 1",
            text_snippet="c.68_69delAG",
            source_precision=SourcePrecision.EXACT,
        ),
        confidence=0.9,
    )

    grounded = SourceGrounder().ground_items(_doc(), [item])

    assert grounded[0].source.page == 2
    assert grounded[0].source.source_precision == SourcePrecision.CORRECTED
    assert grounded[0].raw_source is not None
