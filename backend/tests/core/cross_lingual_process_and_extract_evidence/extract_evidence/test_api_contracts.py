from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    ContentBlock,
    EvidenceChain,
    EvidenceItem,
    EvidenceStatus,
    SourceLocation,
    SpecialEvidenceRecord,
    Track,
    TrackDocument,
)


def test_track_document_carries_minimal_content_blocks():
    doc = TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text="BRCA1 c.5266dupC",
        page_spans=[],
        blocks=[
            ContentBlock(
                type="table",
                page_idx=1,
                bbox=[10, 20, 30, 40],
                table_body="BRCA1 c.5266dupC",
                table_caption=["Table 1"],
            )
        ],
    )

    assert doc.blocks[0].type == "table"
    assert doc.blocks[0].bbox == [10, 20, 30, 40]


def test_source_location_allows_raw_block_only_location():
    source = SourceLocation(
        context_type="table",
        context_ref="Table 1",
        text_snippet="c.5266dupC",
        block_index=3,
        block_type="table",
    )

    assert source.span_id == ""
    assert source.page == 0
    assert source.start_offset == -1
    assert source.end_offset == -1
    assert source.block_index == 3


def test_group_fields_are_public_contracts():
    item = EvidenceItem(
        field_id="A.variant_hgvs_c",
        category="A",
        field_name="HGVS coding variant",
        status=EvidenceStatus.FOUND,
        value="c.5266dupC",
        confidence=0.9,
        group_id="gene=BRCA1|variant=c.5266dupC",
    )
    record = SpecialEvidenceRecord(
        record_type="functional",
        description="Functional assay",
        group_id="gene=BRCA1|variant=c.5266dupC",
    )
    chain = EvidenceChain(
        chain_id="gene=BRCA1|variant=c.5266dupC",
        case_ids=["case-1", "case-2"],
        special_evidence_ids=["special-0"],
    )

    assert item.group_id == "gene=BRCA1|variant=c.5266dupC"
    assert record.group_id == item.group_id
    assert chain.case_ids == ["case-1", "case-2"]
    assert chain.special_evidence_ids == ["special-0"]


def test_result_model_dump_exposes_group_and_chain_fields():
    item = EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.FOUND,
        value="BRCA1",
        confidence=0.9,
        group_id="gene=BRCA1|variant=c.5266dupC",
    )
    result = item.model_dump()

    assert result["group_id"] == "gene=BRCA1|variant=c.5266dupC"
