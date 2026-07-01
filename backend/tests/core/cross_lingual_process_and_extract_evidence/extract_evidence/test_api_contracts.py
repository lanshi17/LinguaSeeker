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
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.api import (
    _filter_evidence_blocks,
    _is_section_heading,
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


def test_is_section_heading_handles_boundaries_and_chinese_headings() -> None:
    assert _is_section_heading("") is False
    assert _is_section_heading("Results") is True
    assert _is_section_heading("REFERENCES") is True
    assert _is_section_heading("结果") is True
    assert _is_section_heading("参考文献") is True
    assert _is_section_heading("Results " + "x" * 121) is False


def test_filter_evidence_blocks_skips_chinese_non_evidence_sections() -> None:
    blocks = [
        {"type": "title", "text": "Rett 综合征的临床特点"},
        {"type": "text", "text": "摘要 MECP2 c.913insT 被检出。"},
        {"type": "text", "text": "结果 5 例患儿存在 MECP2 突变。"},
        {"type": "text", "text": "参考文献"},
        {"type": "text", "text": "[1] 与本文证据无关的引用。"},
        {"type": "text", "text": "致谢"},
        {"type": "text", "text": "感谢测序平台支持。"},
        {"type": "text", "text": "讨论 TRD 区域突变可能影响语言功能。"},
    ]

    filtered = _filter_evidence_blocks(blocks)
    kept_text = "\n".join(str(block.get("text", "")) for block in filtered)

    assert "摘要 MECP2 c.913insT 被检出" in kept_text
    assert "结果 5 例患儿存在 MECP2 突变" in kept_text
    assert "参考文献" not in kept_text
    assert "无关的引用" not in kept_text
    assert "致谢" not in kept_text
    assert "测序平台" not in kept_text
    assert "讨论 TRD 区域突变" in kept_text


def test_filter_evidence_blocks_skips_consecutive_non_evidence_sections_until_evidence_resumes() -> None:
    blocks = [
        {"type": "text", "text": "Abstract MECP2 variants were detected."},
        {"type": "text", "text": "References"},
        {"type": "text", "text": "[1] Citation with unrelated MECP2 text."},
        {"type": "text", "text": "Acknowledgments"},
        {"type": "text", "text": "The authors thank the clinical staff."},
        {"type": "text", "text": "Funding"},
        {"type": "text", "text": "Supported by a local grant."},
        {"type": "text", "text": "Results"},
        {"type": "text", "text": "Five children had pathogenic MECP2 variants."},
    ]

    filtered = _filter_evidence_blocks(blocks)
    kept_text = "\n".join(str(block.get("text", "")) for block in filtered)

    assert "Abstract MECP2 variants were detected" in kept_text
    assert "Citation with unrelated" not in kept_text
    assert "clinical staff" not in kept_text
    assert "local grant" not in kept_text
    assert "Results" in kept_text
    assert "Five children had pathogenic MECP2 variants" in kept_text


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


def test_build_dual_documents_loads_translation_alignment(tmp_path) -> None:
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.api import (
        EvidenceExtractionService,
    )

    original_payload = {
        "metadata": {"doc_id": "doc-align", "source_language": "zh"},
        "formatted_text": "患者表现出严重的呼吸衰竭。\n基因检测提示ABCA3缺陷引起的间质性肺病。",
        "blocks": [],
    }
    translated_payload = {
        "metadata": {
            "doc_id": "doc-align",
            "source_language": "zh",
            "translation_alignment": [
                {
                    "chunk_id": "c_0002",
                    "original_text": "基因检测提示ABCA3缺陷引起的间质性肺病。",
                    "english_text": ("Genetic testing suggested interstitial lung disease due to ABCA3 deficiency."),
                    "original_start_offset": 15,
                    "original_end_offset": 39,
                    "english_start_offset": 54,
                    "english_end_offset": 127,
                    "page": 1,
                    "block_index": 1,
                }
            ],
        },
        "formatted_text": (
            "The patient presented with severe respiratory failure.\n"
            "Genetic testing suggested interstitial lung disease due to ABCA3 deficiency."
        ),
        "blocks": [],
    }
    (tmp_path / "original.json").write_text(json.dumps(original_payload), encoding="utf-8")
    (tmp_path / "translated.json").write_text(json.dumps(translated_payload), encoding="utf-8")

    docs = EvidenceExtractionService.build_dual_documents_from_output_dir(tmp_path)

    assert docs.translated.translation_alignment[0].chunk_id == "c_0002"
    assert docs.translated.translation_alignment[0].original_start_offset == 15
    assert docs.translated.translation_alignment[0].english_text.endswith("ABCA3 deficiency.")


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
        "formatted_text": "\n".join(
            [
                "Abstract MECP2 c.913insT was detected.",
                "Results Five children had MECP2 variants.",
                "References",
                "[1] Amir RE. MECP2 unrelated citation.",
                "Acknowledgments",
                "We thank the sequencing facility.",
            ]
        ),
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
