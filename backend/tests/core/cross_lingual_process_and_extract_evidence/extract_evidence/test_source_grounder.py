from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    ContentBlock,
    EvidenceItem,
    EvidenceStatus,
    PageSpan,
    SourceLocation,
    SpecialEvidenceRecord,
    Track,
    TrackDocument,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.core import SourceGrounder


def _doc() -> TrackDocument:
    text = "Intro\nBRCA1 c.5266dupC\nFigure caption loss of function"
    return TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text=text,
        page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=len(text))],
        blocks=[
            ContentBlock(type="text", page_idx=0, text="Intro", bbox=[0, 0, 10, 10]),
            ContentBlock(type="table", page_idx=0, table_body="BRCA1 c.5266dupC", bbox=[10, 10, 20, 20]),
            ContentBlock(type="chart", page_idx=0, content="Figure caption loss of function", bbox=[20, 20, 30, 30]),
        ],
    )


def test_grounder_uses_block_bbox_and_type():
    item = EvidenceItem(
        field_id="A.variant_hgvs_c",
        category="A",
        field_name="HGVS coding variant",
        status=EvidenceStatus.FOUND,
        value="c.5266dupC",
        confidence=0.9,
        raw_source=SourceLocation(block_index=1, context_type="table", context_ref="", text_snippet="c.5266dupC"),
    )

    grounded = SourceGrounder().ground_items(_doc(), [item])[0]

    assert grounded.source is not None
    assert grounded.source.block_index == 1
    assert grounded.source.bbox == [10, 10, 20, 20]
    assert grounded.source.block_type == "table"


def test_grounder_corrects_wrong_llm_block_index_from_text_match():
    item = EvidenceItem(
        field_id="A.variant_hgvs_c",
        category="A",
        field_name="HGVS coding variant",
        status=EvidenceStatus.FOUND,
        value="c.5266dupC",
        confidence=0.9,
        raw_source=SourceLocation(block_index=0, context_type="text", context_ref="", text_snippet="c.5266dupC"),
    )

    grounded = SourceGrounder().ground_items(_doc(), [item])[0]

    assert grounded.raw_source.block_index == 0
    assert grounded.source.block_index == 1
    assert grounded.source.bbox == [10, 10, 20, 20]


def test_grounder_falls_back_to_pure_text_without_blocks():
    text = "BRCA1 c.5266dupC"
    doc = TrackDocument(
        document_id="old-doc",
        track=Track.ORIGINAL,
        formatted_text=text,
        page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=len(text))],
        blocks=[],
    )
    item = EvidenceItem(
        field_id="A.variant_hgvs_c",
        category="A",
        field_name="HGVS coding variant",
        status=EvidenceStatus.FOUND,
        value="c.5266dupC",
        confidence=0.9,
        raw_source=SourceLocation(context_type="text", context_ref="", text_snippet="c.5266dupC"),
    )

    grounded = SourceGrounder().ground_items(doc, [item])[0]

    assert grounded.source.start_offset >= 0
    assert grounded.source.block_index == -1


def test_grounder_keeps_table_caption_hit_as_found():
    text = "Table 1. Variants"
    doc = TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text=text,
        page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=len(text))],
        blocks=[ContentBlock(type="table", page_idx=0, table_caption=["Table 1. Variants"], bbox=[1, 2, 3, 4])],
    )
    item = EvidenceItem(
        field_id="J.known_pathogenic_variant_reference",
        category="J",
        field_name="Known pathogenic variant reference",
        status=EvidenceStatus.FOUND,
        value="Table 1",
        confidence=0.9,
        raw_source=SourceLocation(block_index=0, context_type="table", context_ref="Table 1. Variants", text_snippet="Table 1. Variants"),
    )

    grounded = SourceGrounder().ground_items(doc, [item])[0]

    assert grounded.status == EvidenceStatus.FOUND
    assert grounded.source.block_type == "table"


def test_grounder_marks_image_miss_as_ocr_gap():
    doc = _doc()
    item = EvidenceItem(
        field_id="F.functional_result",
        category="F",
        field_name="Functional result",
        status=EvidenceStatus.FOUND,
        value="missing gel band",
        confidence=0.7,
        raw_source=SourceLocation(block_index=2, context_type="figure", context_ref="Figure 1", text_snippet="missing gel band"),
    )

    grounded = SourceGrounder().ground_items(doc, [item])[0]

    assert grounded.status == EvidenceStatus.OCR_GAP


def test_grounder_preserves_special_record_on_failure_with_no_source():
    doc = _doc()
    record = SpecialEvidenceRecord(
        record_type="functional",
        description="Missing figure evidence",
        raw_source=SourceLocation(block_index=2, context_type="figure", context_ref="Figure 1", text_snippet="not present"),
        group_id="gene=BRCA1|variant=c.5266dupC",
    )

    grounded = SourceGrounder().ground_special_records(doc, [record])[0]

    assert grounded.source is None
    assert grounded.raw_source is not None
