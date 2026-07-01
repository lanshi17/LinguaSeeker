from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    ContentBlock,
    EvidenceItem,
    EvidenceStatus,
    SourceLocation,
    SpecialEvidenceRecord,
    Track,
    TrackDocument,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.core import GroupAssigner


def _item(field_id: str, value: str, block_index: int = 0) -> EvidenceItem:
    return EvidenceItem(
        field_id=field_id,
        category=field_id.split(".")[0],
        field_name=field_id,
        status=EvidenceStatus.FOUND,
        value=value,
        confidence=0.9,
        raw_source=SourceLocation(block_index=block_index, context_type="text", context_ref="", text_snippet=value),
    )


def test_group_assigner_uses_gene_variant_key():
    doc = TrackDocument(document_id="doc-1", track=Track.ORIGINAL, formatted_text="", page_spans=[])
    items = [
        _item("A.gene_symbol", "BRCA1"),
        _item("A.variant_hgvs_c", "c.5266dupC"),
    ]

    grouped_items, grouped_special = GroupAssigner().assign(doc, items, [])

    assert {item.group_id for item in grouped_items} == {"gene=BRCA1|variant=c.5266dupC"}
    assert grouped_special == []


def test_group_assigner_merges_same_normalized_variant():
    doc = TrackDocument(document_id="doc-1", track=Track.ORIGINAL, formatted_text="", page_spans=[])
    items = [
        _item("A.gene_symbol", "BRCA1"),
        _item("A.variant_hgvs_c", " c.5266dupC "),
        _item("B.case_id", "case-1"),
        _item("B.case_id", "case-2"),
    ]

    grouped_items, _ = GroupAssigner().assign(doc, items, [])

    assert {item.group_id for item in grouped_items} == {"gene=BRCA1|variant=c.5266dupC"}


def test_group_assigner_gene_only_group_uses_missing_variant():
    doc = TrackDocument(document_id="doc-1", track=Track.ORIGINAL, formatted_text="", page_spans=[])
    grouped_items, _ = GroupAssigner().assign(doc, [_item("A.gene_symbol", "GLA")], [])

    assert grouped_items[0].group_id == "gene=GLA|variant=__missing__"


def test_group_assigner_variant_only_uses_document_gene_context():
    doc = TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text="GLA c.679C>T",
        page_spans=[],
        blocks=[ContentBlock(type="text", page_idx=0, text="GLA c.679C>T")],
    )
    items = [_item("A.variant_hgvs_c", "c.679C>T", block_index=0)]

    grouped_items, _ = GroupAssigner().assign(doc, items, [])

    assert grouped_items[0].group_id == "gene=GLA|variant=c.679C>T"


def test_group_assigner_assigns_special_records_to_existing_group():
    doc = TrackDocument(document_id="doc-1", track=Track.ORIGINAL, formatted_text="", page_spans=[])
    items = [_item("A.gene_symbol", "BRCA1"), _item("A.variant_hgvs_c", "c.5266dupC")]
    records = [
        SpecialEvidenceRecord(
            record_type="functional",
            description="BRCA1 c.5266dupC showed loss of function",
            raw_source=SourceLocation(
                block_index=0, context_type="text", context_ref="", text_snippet="loss of function"
            ),
        )
    ]

    _, grouped_special = GroupAssigner().assign(doc, items, records)

    assert grouped_special[0].group_id == "gene=BRCA1|variant=c.5266dupC"


def test_group_assigner_falls_back_to_nearest_group_for_special_records():
    doc = TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text="",
        page_spans=[],
        blocks=[
            ContentBlock(type="text", page_idx=0, text="BRCA1 c.5266dupC"),
            ContentBlock(type="text", page_idx=1, text="GLA c.679C>T"),
            ContentBlock(type="text", page_idx=2, text="Functional assay result"),
        ],
    )
    items = [
        _item("A.gene_symbol", "BRCA1", block_index=0),
        _item("A.variant_hgvs_c", "c.5266dupC", block_index=0),
        _item("A.gene_symbol", "GLA", block_index=1),
        _item("A.variant_hgvs_c", "c.679C>T", block_index=1),
    ]
    records = [
        SpecialEvidenceRecord(
            record_type="functional",
            description="Assay result did not restate gene or variant",
            raw_source=SourceLocation(block_index=2, context_type="text", context_ref="", text_snippet="Assay result"),
        )
    ]

    _, grouped_special = GroupAssigner().assign(doc, items, records)

    assert grouped_special[0].group_id == "gene=GLA|variant=c.679C>T"


def test_group_assigner_does_not_emit_orphan_gene_only_group_when_variant_group_exists():
    doc = TrackDocument(document_id="doc-1", track=Track.ORIGINAL, formatted_text="", page_spans=[])
    items = [
        _item("A.gene_symbol", "BRCA1", block_index=0),
        _item("A.variant_hgvs_c", "c.5266dupC", block_index=0),
        _item("B.disease_diagnosis", "BRCA1-associated cancer", block_index=1),
    ]

    grouped_items, _ = GroupAssigner().assign(doc, items, [])

    assert {item.group_id for item in grouped_items} == {"gene=BRCA1|variant=c.5266dupC"}
