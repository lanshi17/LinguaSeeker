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

import json



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
def test_build_dual_documents_accepts_extraction_target(tmp_path) -> None:
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.api import (
        EvidenceExtractionService,
    )
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
        ExtractionTarget,
    )

    payload = {
        "metadata": {"doc_id": "doc-target", "source_language": "en"},
        "formatted_text": "ABCA3 and CFTR are both mentioned.",
        "blocks": [],
    }
    (tmp_path / "original.json").write_text(json.dumps(payload), encoding="utf-8")
    (tmp_path / "translated.json").write_text(json.dumps(payload), encoding="utf-8")

    target = ExtractionTarget(gene_symbol="ABCA3", disease_name="ABCA3 deficiency")
    docs = EvidenceExtractionService.build_dual_documents_from_output_dir(tmp_path, target)

    assert docs.original.extraction_target == target
    assert docs.translated.extraction_target == target


def test_build_dual_documents_target_optional(tmp_path) -> None:
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.api import (
        EvidenceExtractionService,
    )

    payload = {
        "metadata": {"doc_id": "doc-no-target", "source_language": "en"},
        "formatted_text": "No target.",
        "blocks": [],
    }
    (tmp_path / "original.json").write_text(json.dumps(payload), encoding="utf-8")
    (tmp_path / "translated.json").write_text(json.dumps(payload), encoding="utf-8")

    docs = EvidenceExtractionService.build_dual_documents_from_output_dir(tmp_path)

    assert docs.original.extraction_target is None
    assert docs.translated.extraction_target is None


def test_build_dual_documents_skips_non_evidence_sections(tmp_path) -> None:
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.api import (
        EvidenceExtractionService,
    )

    payload = {
        "metadata": {"doc_id": "doc-sections", "source_language": "en"},
        "blocks": [
            {"type": "title", "text": "Clinical features and MECP2 mutations"},
            {"type": "text", "text": "Abstract MECP2 c.913insT was detected."},
            {"type": "text", "text": "Results Five children had MECP2 variants."},
            {"type": "text", "text": "References"},
            {"type": "text", "text": "[1] Amir RE. MECP2 unrelated citation."},
            {"type": "text", "text": "Acknowledgments"},
            {"type": "text", "text": "We thank the sequencing facility."},
            {"type": "text", "text": "Conflict of Interest"},
            {"type": "text", "text": "The authors declare no conflict of interest."},
        ],
    }
    (tmp_path / "original.json").write_text(json.dumps(payload), encoding="utf-8")
    (tmp_path / "translated.json").write_text(json.dumps(payload), encoding="utf-8")

    docs = EvidenceExtractionService.build_dual_documents_from_output_dir(tmp_path)

    assert "MECP2 c.913insT was detected" in docs.original.formatted_text
    assert "Five children had MECP2 variants" in docs.original.formatted_text
    assert "References" not in docs.original.formatted_text
    assert "Amir RE" not in docs.original.formatted_text
    assert "Acknowledgments" not in docs.original.formatted_text
    assert "Conflict of Interest" not in docs.original.formatted_text


def test_build_dual_documents_skips_non_evidence_sections_in_formatted_text(tmp_path) -> None:
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.api import (
        EvidenceExtractionService,
    )

    payload = {
        "metadata": {"doc_id": "doc-formatted-sections", "source_language": "en"},
        "formatted_text": "\n".join([
            "Abstract MECP2 c.913insT was detected.",
            "Results Five children had MECP2 variants.",
            "References",
            "[1] Amir RE. MECP2 unrelated citation.",
            "Acknowledgments",
            "We thank the sequencing facility.",
        ]),
        "blocks": [],
    }
    (tmp_path / "original.json").write_text(json.dumps(payload), encoding="utf-8")
    (tmp_path / "translated.json").write_text(json.dumps(payload), encoding="utf-8")

    docs = EvidenceExtractionService.build_dual_documents_from_output_dir(tmp_path)

    assert "MECP2 c.913insT was detected" in docs.original.formatted_text
    assert "Five children had MECP2 variants" in docs.original.formatted_text
    assert "References" not in docs.original.formatted_text
    assert "Amir RE" not in docs.original.formatted_text
    assert "Acknowledgments" not in docs.original.formatted_text
