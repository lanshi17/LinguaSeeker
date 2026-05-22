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


def test_source_grounding_marks_snippet_not_found_as_source_invalid():
    item = EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.FOUND,
        value="TP53",
        source=SourceLocation(
            span_id="p1",
            page=1,
            start_offset=0,
            end_offset=4,
            context_type="text",
            context_ref="Results",
            text_snippet="TP53",
            source_precision=SourcePrecision.EXACT,
        ),
        confidence=0.9,
    )

    grounded = SourceGrounder().ground_items(_doc(), [item])

    assert grounded[0].status == EvidenceStatus.SOURCE_INVALID
    assert grounded[0].raw_source is not None
    assert grounded[0].raw_source.text_snippet == "TP53"


def test_source_grounding_marks_missing_image_source_as_ocr_gap():
    item = EvidenceItem(
        field_id="A.variant_hgvs_p",
        category="A",
        field_name="HGVS protein variant",
        status=EvidenceStatus.FOUND,
        value="p.R227X",
        source=SourceLocation(
            span_id="fig-1",
            page=2,
            start_offset=0,
            end_offset=6,
            context_type="figure",
            context_ref="Figure 1",
            text_snippet="p.R227X",
            block_type="image",
            source_precision=SourcePrecision.EXACT,
        ),
        confidence=0.9,
        inference_basis=["Variant appears in sequencing trace image."],
    )

    grounded = SourceGrounder().ground_items(_doc(), [item])

    assert grounded[0].status == EvidenceStatus.OCR_GAP
    assert grounded[0].raw_source is not None
    assert grounded[0].inference_basis == ["Variant appears in sequencing trace image."]
