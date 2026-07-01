from unittest.mock import MagicMock

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    ContentBlock,
    DocumentEvidenceMap,
    EvidenceItem,
    EvidenceStatus,
    ExtractionTarget,
    PageSpan,
    QualityReport,
    SourceLocation,
    SourcePrecision,
    SpecialEvidenceResponse,
    Track,
    TrackDocument,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.providers import (
    EvidenceModelTier,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.catalog_extraction import (
    CatalogExtractionStage,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.evidence_map import RelevanceScanStage
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.quality_validation import (
    QualityGateStage,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.source_grounding import (
    SourceGroundingStage,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.special_evidence import (
    SpecialEvidenceStage,
)


def _doc() -> TrackDocument:
    return TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text="Patient 1 had Fabry disease and carried a hemizygous GLA c.1000G>A variant.",
        page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=78)],
        blocks=[
            ContentBlock(
                type="table",
                page_idx=0,
                table_caption=["Table 1. Variants"],
                table_body="Patient 1 had Fabry disease and carried a hemizygous GLA c.1000G>A variant.",
            )
        ],
    )


def test_evidence_map_stage_calls_fast_tier():
    provider = MagicMock()
    emap = DocumentEvidenceMap(relevant=True, gene_terms=["GLA"])
    provider.invoke_structured.return_value = emap

    stage = RelevanceScanStage(provider)
    result = stage.run(_doc())

    assert result.evidence_map.relevant is True
    provider.invoke_structured.assert_called_once()
    call_kwargs = provider.invoke_structured.call_args
    assert call_kwargs.kwargs["tier"] == EvidenceModelTier.FAST
    assert call_kwargs.kwargs["response_method"] == "json_mode"


def test_catalog_extraction_stage_calls_strong_tier():
    provider = MagicMock()
    item = EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.FOUND,
        value="GLA",
        confidence=0.9,
        source=SourceLocation(
            span_id="p1",
            page=1,
            start_offset=38,
            end_offset=41,
            context_type="text",
            context_ref="",
            text_snippet="GLA",
            source_precision=SourcePrecision.EXACT,
        ),
    )
    provider.invoke_structured.return_value = [item]

    stage = CatalogExtractionStage(provider)
    result = stage.run(_doc(), DocumentEvidenceMap(relevant=True))

    assert len(result) == 1
    assert result[0].value == "GLA"
    assert result[0].source is None
    assert result[0].raw_source is not None
    call_kwargs = provider.invoke_structured.call_args
    assert call_kwargs.kwargs["tier"] == EvidenceModelTier.STRONG
    assert "[Block 0 | table | page 1 | caption: Table 1. Variants]" in call_kwargs.kwargs["prompt"]


def test_catalog_extraction_stage_uses_target_recall_first_block_selection() -> None:
    provider = MagicMock()
    provider.invoke_structured.return_value = []
    document = TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text="",
        page_spans=[],
        blocks=[
            ContentBlock(text="Administrative header without target evidence."),
            ContentBlock(
                text=(
                    "Biallelic pathogenic variants in ABCB4 cause progressive familial intrahepatic cholestasis type 3."
                ),
            ),
        ],
        extraction_target=ExtractionTarget(
            gene_symbol="ABCB4",
            disease_name="progressive familial intrahepatic cholestasis type 3",
        ),
    )

    CatalogExtractionStage(provider).run(document, DocumentEvidenceMap(relevant=True))

    prompts = [call.kwargs["prompt"] for call in provider.invoke_structured.call_args_list]
    assert prompts
    assert all("[Block 1 | text | page 1]" in prompt for prompt in prompts)
    assert all("[Block 0 | text | page 1]" in prompt for prompt in prompts)
    assert all("Administrative header without target evidence" in prompt for prompt in prompts)


def test_catalog_extraction_stage_scopes_target_catalog_to_eligible_fields() -> None:
    provider = MagicMock()
    provider.invoke_structured.return_value = []
    document = TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text="",
        page_spans=[],
        blocks=[
            ContentBlock(
                text="ABCA3 deficiency is caused by biallelic pathogenic changes in ABCA3.",
            ),
        ],
        extraction_target=ExtractionTarget(
            gene_symbol="ABCA3",
            disease_name="ABCA3 deficiency",
        ),
    )

    CatalogExtractionStage(provider).run(document, DocumentEvidenceMap(relevant=True))

    # First call is the normal catalog extraction; retry may fire a second call
    assert provider.invoke_structured.call_count >= 1
    call = provider.invoke_structured.call_args_list[0]
    assert call.kwargs["stage"] == "catalog_extraction/high_signal"
    prompt = call.kwargs["prompt"]
    catalog_text = prompt.split("EVIDENCE CATALOG", maxsplit=1)[1].split("RULES:", maxsplit=1)[0]
    assert "A.gene_symbol" in catalog_text
    assert "A.gene_disease_relationship" in catalog_text
    assert "B.disease_diagnosis" in catalog_text
    assert "A.variant_hgvs_c" not in catalog_text
    assert "F.functional_result" not in catalog_text


def test_special_evidence_stage_calls_strong_tier():
    provider = MagicMock()
    provider.invoke_structured.return_value = []

    stage = SpecialEvidenceStage(provider)
    result = stage.run(_doc(), [])

    assert result == []
    call_kwargs = provider.invoke_structured.call_args
    assert call_kwargs.kwargs["tier"] == EvidenceModelTier.STRONG
    assert call_kwargs.kwargs["response_method"] == "json_mode"
    assert "[Block 0 | table | page 1 | caption: Table 1. Variants]" in call_kwargs.kwargs["prompt"]


def test_special_evidence_stage_filters_untraceable_case_control_records():
    provider = MagicMock()
    provider.invoke_structured.return_value = [
        {
            "record_type": "case_control",
            "description": "A large screening study included [REDACTED] patients.",
            "evidence_field_ids": ["B.case_count"],
            "source": {
                "span_id": "s1",
                "page": 1,
                "start_offset": 0,
                "end_offset": 0,
                "context_type": "text",
                "context_ref": "Discussion",
                "text_snippet": "A large screening study included [REDACTED] patients.",
                "source_precision": "ambiguous",
            },
            "confidence": 0.8,
        }
    ]

    stage = SpecialEvidenceStage(provider)
    result = stage.run(_doc(), [])

    assert result == []


def test_special_evidence_stage_keeps_case_control_records_for_g_fields():
    provider = MagicMock()
    provider.invoke_structured.return_value = [
        {
            "record_type": "case_control",
            "description": "A case-control study reported enrichment in affected cases.",
            "evidence_field_ids": ["G.case_count", "G.control_count"],
            "source": {
                "span_id": "s1",
                "page": 1,
                "start_offset": 14,
                "end_offset": 27,
                "context_type": "text",
                "context_ref": "Results",
                "text_snippet": "Fabry disease",
                "source_precision": "exact",
            },
            "confidence": 0.8,
        }
    ]

    text = _doc().formatted_text
    start = text.index("Fabry disease")
    stage = SpecialEvidenceStage(provider)
    result = stage.run(
        _doc(),
        [
            EvidenceItem(
                field_id="G.case_count",
                category="G",
                field_name="Case count",
                status=EvidenceStatus.FOUND,
                value="12",
                confidence=0.9,
                source=SourceLocation(
                    span_id="p1",
                    page=1,
                    start_offset=start,
                    end_offset=start + len("Fabry disease"),
                    context_type="text",
                    context_ref="",
                    text_snippet="Fabry disease",
                ),
            ),
            EvidenceItem(
                field_id="G.control_count",
                category="G",
                field_name="Control count",
                status=EvidenceStatus.FOUND,
                value="8",
                confidence=0.9,
                source=SourceLocation(
                    span_id="p1",
                    page=1,
                    start_offset=start,
                    end_offset=start + len("Fabry disease"),
                    context_type="text",
                    context_ref="",
                    text_snippet="Fabry disease",
                ),
            ),
            EvidenceItem(
                field_id="G.control_count",
                category="G",
                field_name="Control count",
                status=EvidenceStatus.FOUND,
                value="8",
                confidence=0.9,
                source=SourceLocation(
                    span_id="p1",
                    page=1,
                    start_offset=start,
                    end_offset=start + len("Fabry disease"),
                    context_type="text",
                    context_ref="",
                    text_snippet="Fabry disease",
                ),
            ),
        ],
    )

    assert len(result) == 1
    assert result[0].record_type == "case_control"


def test_special_evidence_stage_rejects_short_untraceable_snippet():
    provider = MagicMock()
    provider.invoke_structured.return_value = [
        {
            "record_type": "authority",
            "description": "Short snippet should not be traceable by substring fallback.",
            "evidence_field_ids": ["J.known_pathogenic_variant_reference"],
            "source": {
                "span_id": "s1",
                "page": 1,
                "start_offset": 0,
                "end_offset": 3,
                "context_type": "text",
                "context_ref": "Discussion",
                "text_snippet": "GLA",
                "source_precision": "exact",
            },
            "confidence": 0.8,
        }
    ]

    stage = SpecialEvidenceStage(provider)
    result = stage.run(
        _doc(),
        [
            EvidenceItem(
                field_id="J.known_pathogenic_variant_reference",
                category="J",
                field_name="Known pathogenic variant reference",
                status=EvidenceStatus.FOUND,
                value="GLA is pathogenic",
                confidence=0.9,
                source=SourceLocation(
                    span_id="p1",
                    page=1,
                    start_offset=38,
                    end_offset=41,
                    context_type="text",
                    context_ref="",
                    text_snippet="GLA",
                ),
            )
        ],
    )

    assert result == []


def test_special_evidence_stage_keeps_valid_authority_for_found_field():
    provider = MagicMock()
    current_item = EvidenceItem(
        field_id="J.known_pathogenic_variant_reference",
        category="J",
        field_name="Known pathogenic variant reference",
        status=EvidenceStatus.FOUND,
        value="p.R227X is pathogenic",
        confidence=0.9,
        source=SourceLocation(
            span_id="p1",
            page=1,
            start_offset=0,
            end_offset=10,
            context_type="text",
            context_ref="",
            text_snippet="Patient 1",
        ),
    )
    provider.invoke_structured.return_value = [
        {
            "record_type": "authority",
            "description": "p.R227X is a known pathogenic variant.",
            "evidence_field_ids": ["J.known_pathogenic_variant_reference"],
            "source": {
                "span_id": "p1",
                "page": 1,
                "start_offset": 0,
                "end_offset": 9,
                "context_type": "text",
                "context_ref": "Discussion",
                "text_snippet": "Patient 1",
                "source_precision": "exact",
            },
            "confidence": 0.9,
        }
    ]

    stage = SpecialEvidenceStage(provider)
    result = stage.run(_doc(), [current_item])

    assert len(result) == 1
    assert result[0].record_type == "authority"
    assert result[0].source is None
    assert result[0].raw_source is not None


def test_special_evidence_stage_filters_source_snippet_not_in_document():
    provider = MagicMock()
    current_item = EvidenceItem(
        field_id="J.known_pathogenic_variant_reference",
        category="J",
        field_name="Known pathogenic variant reference",
        status=EvidenceStatus.FOUND,
        value="p.R227X is pathogenic",
        confidence=0.9,
        source=SourceLocation(
            span_id="p1",
            page=1,
            start_offset=0,
            end_offset=9,
            context_type="text",
            context_ref="",
            text_snippet="Patient 1",
        ),
    )
    provider.invoke_structured.return_value = [
        {
            "record_type": "authority",
            "description": "p.R227X is a known pathogenic variant.",
            "evidence_field_ids": ["J.known_pathogenic_variant_reference"],
            "source": {
                "span_id": "p1",
                "page": 1,
                "start_offset": 10,
                "end_offset": 20,
                "context_type": "text",
                "context_ref": "Discussion",
                "text_snippet": "not in document",
                "source_precision": "exact",
            },
            "confidence": 0.9,
        }
    ]

    stage = SpecialEvidenceStage(provider)
    result = stage.run(_doc(), [current_item])

    assert result == []


def test_special_evidence_stage_keeps_traceable_authority_with_zero_offsets():
    provider = MagicMock()
    current_item = EvidenceItem(
        field_id="J.known_pathogenic_variant_reference",
        category="J",
        field_name="Known pathogenic variant reference",
        status=EvidenceStatus.FOUND,
        value="p.R227X is pathogenic",
        confidence=0.9,
        source=SourceLocation(
            span_id="p1",
            page=1,
            start_offset=0,
            end_offset=13,
            context_type="text",
            context_ref="Discussion",
            text_snippet="Fabry disease",
        ),
    )
    provider.invoke_structured.return_value = [
        {
            "record_type": "authority",
            "description": "Fabry disease has an expert consensus in China.",
            "evidence_field_ids": ["J.known_pathogenic_variant_reference"],
            "source": {
                "span_id": "disc-1",
                "page": 1,
                "start_offset": 0,
                "end_offset": 0,
                "context_type": "text",
                "context_ref": "Discussion",
                "text_snippet": "Fabry disease",
                "source_precision": "exact",
            },
            "confidence": 0.9,
        }
    ]

    stage = SpecialEvidenceStage(provider)
    result = stage.run(_doc(), [current_item])

    assert len(result) == 1
    assert result[0].record_type == "authority"
    assert result[0].raw_source is not None


def test_special_evidence_stage_keeps_caption_sourced_record_before_grounding():
    provider = MagicMock()
    provider.invoke_structured.return_value = [
        {
            "record_type": "authority",
            "description": "Caption-carried authority evidence.",
            "evidence_field_ids": ["J.known_pathogenic_variant_reference"],
            "source": {
                "block_index": 0,
                "context_type": "table",
                "context_ref": "Table 1. Variants",
                "text_snippet": "Table 1. Variants",
            },
            "confidence": 0.9,
        }
    ]
    current_item = EvidenceItem(
        field_id="J.known_pathogenic_variant_reference",
        category="J",
        field_name="Known pathogenic variant reference",
        status=EvidenceStatus.FOUND,
        value="variant reference",
        confidence=0.9,
        raw_source=SourceLocation(
            block_index=0,
            context_type="table",
            context_ref="Table 1. Variants",
            text_snippet="Table 1. Variants",
        ),
    )

    result = SpecialEvidenceStage(provider).run(_doc(), [current_item])

    assert len(result) == 1
    assert result[0].raw_source is not None


def test_special_evidence_stage_keeps_non_g_case_control_when_document_text_is_traceable():
    provider = MagicMock()
    provider.invoke_structured.return_value = [
        {
            "record_type": "case_control",
            "description": "A retrospective analysis reported Fabry disease progression rates.",
            "evidence_field_ids": ["B.disease_diagnosis", "B.clinical_phenotypes"],
            "source": {
                "span_id": "disc-2",
                "page": 1,
                "start_offset": 0,
                "end_offset": 0,
                "context_type": "text",
                "context_ref": "Discussion",
                "text_snippet": "Fabry disease",
                "source_precision": "exact",
            },
            "confidence": 0.8,
        }
    ]
    current_items = [
        EvidenceItem(
            field_id="B.disease_diagnosis",
            category="B",
            field_name="Disease diagnosis",
            status=EvidenceStatus.FOUND,
            value="Fabry disease",
            confidence=0.9,
            source=SourceLocation(
                span_id="p1",
                page=1,
                start_offset=14,
                end_offset=27,
                context_type="text",
                context_ref="",
                text_snippet="Fabry disease",
            ),
        ),
        EvidenceItem(
            field_id="B.clinical_phenotypes",
            category="B",
            field_name="Key clinical phenotypes",
            status=EvidenceStatus.FOUND,
            value="Fabry disease",
            confidence=0.9,
            source=SourceLocation(
                span_id="p1",
                page=1,
                start_offset=14,
                end_offset=27,
                context_type="text",
                context_ref="",
                text_snippet="Fabry disease",
            ),
        ),
    ]

    stage = SpecialEvidenceStage(provider)
    result = stage.run(_doc(), current_items)

    assert len(result) == 1
    assert result[0].record_type == "case_control"
    assert result[0].raw_source is not None


def test_source_grounding_stage_uses_grounder():
    text = "Patient 1 had Fabry disease and carried a hemizygous GLA c.1000G>A variant."
    gla_start = text.index("GLA")
    item = EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.FOUND,
        value="GLA",
        source=SourceLocation(
            span_id="p1",
            page=1,
            start_offset=gla_start,
            end_offset=gla_start + 3,
            context_type="text",
            context_ref="",
            text_snippet="GLA",
            source_precision=SourcePrecision.EXACT,
        ),
        confidence=0.9,
    )

    stage = SourceGroundingStage()
    result, special = stage.run(_doc(), [item], [])

    assert special == []
    assert result[0].source.source_precision == SourcePrecision.EXACT


def test_quality_validation_stage_returns_report():
    item = EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.FOUND,
        value="GLA",
        source=SourceLocation(
            span_id="p1",
            page=1,
            start_offset=38,
            end_offset=41,
            context_type="text",
            context_ref="",
            text_snippet="GLA",
            source_precision=SourcePrecision.EXACT,
        ),
        confidence=0.9,
    )

    stage = QualityGateStage()
    report = stage.run([item], contradictions=[], chains=[], special_records=[])

    assert isinstance(report, QualityReport)
    assert report.passed is True


def test_evidence_map_stage_chunks_long_document_and_merges_maps():
    provider = MagicMock()
    call_count = 0

    def _invoke_map(**kwargs):  # noqa: ANN003
        nonlocal call_count
        call_count += 1
        is_later_chunk = call_count > 1
        return DocumentEvidenceMap(
            relevant=is_later_chunk,
            gene_terms=["GLA", "BRCA1"] if is_later_chunk else ["GLA"],
            variant_terms=["c.5266dupC"] if is_later_chunk else [],
        )

    provider.invoke_structured.side_effect = _invoke_map
    document = TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text="\n\n".join(
            [
                "GLA " + ("A" * 160),
                "BRCA1 c.5266dupC " + ("B" * 160),
            ]
        ),
        page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=400)],
    )

    stage = RelevanceScanStage(provider, input_budget_tokens=300)
    result = stage.run(document)

    assert result.evidence_map.relevant is True
    assert result.evidence_map.gene_terms == ["GLA", "BRCA1"]
    assert result.evidence_map.variant_terms == ["c.5266dupC"]
    assert provider.invoke_structured.call_count >= 2
    assert all(call.kwargs["stage"].startswith("relevance_scan/") for call in provider.invoke_structured.call_args_list)


def test_catalog_extraction_stage_chunks_block_prompts_and_keeps_global_block_indices():
    provider = MagicMock()

    def _invoke_catalog(**kwargs):  # noqa: ANN003
        prompt = kwargs["prompt"]
        if "[Block 2 | table | page 3]" in prompt:
            return [
                EvidenceItem(
                    field_id="A.variant_hgvs_c",
                    category="A",
                    field_name="HGVS coding variant",
                    status=EvidenceStatus.FOUND,
                    value="c.1000G>A",
                    confidence=0.9,
                    source=SourceLocation(
                        block_index=2,
                        context_type="table",
                        context_ref="",
                        text_snippet="c.1000G>A",
                    ),
                ),
            ]
        if "[Block 0 | text | page 1]" in prompt:
            return [
                EvidenceItem(
                    field_id="A.gene_symbol",
                    category="A",
                    field_name="Gene symbol",
                    status=EvidenceStatus.FOUND,
                    value="GLA",
                    confidence=0.8,
                    source=SourceLocation(
                        block_index=0,
                        context_type="text",
                        context_ref="",
                        text_snippet="GLA",
                    ),
                ),
            ]
        return []

    provider.invoke_structured.side_effect = _invoke_catalog
    document = TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text="",
        page_spans=[],
        blocks=[
            ContentBlock(type="text", page_idx=0, text="GLA " + ("A" * 160)),
            ContentBlock(type="text", page_idx=1, text="middle " + ("B" * 160)),
            ContentBlock(type="table", page_idx=2, table_body="c.1000G>A " + ("C" * 160)),
        ],
    )

    result = CatalogExtractionStage(provider, input_budget_tokens=2520).run(
        document,
        DocumentEvidenceMap(relevant=True, gene_terms=["GLA"]),
    )

    assert provider.invoke_structured.call_count >= 2
    prompts = [call.kwargs["prompt"] for call in provider.invoke_structured.call_args_list]
    assert "[Block 0 | text | page 1]" in "\n".join(prompts)
    assert "[Block 2 | table | page 3]" in "\n".join(prompts)
    assert all(
        call.kwargs["stage"].startswith("catalog_extraction/") for call in provider.invoke_structured.call_args_list
    )
    assert {item.value for item in result} == {"GLA", "c.1000G>A"}
    assert all(item.source is None for item in result)
    assert all(item.raw_source is not None for item in result)


def test_special_evidence_stage_chunks_long_document_prompts():
    provider = MagicMock()
    provider.invoke_structured.side_effect = [
        SpecialEvidenceResponse(records=[]),
        SpecialEvidenceResponse(records=[]),
    ]
    current_item = EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.FOUND,
        value="GLA",
        confidence=0.9,
        raw_source=SourceLocation(
            block_index=0,
            context_type="text",
            context_ref="",
            text_snippet="GLA",
        ),
    )
    document = TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text="",
        page_spans=[],
        blocks=[
            ContentBlock(type="text", page_idx=0, text="GLA " + ("A" * 160)),
            ContentBlock(type="text", page_idx=1, text="functional assay " + ("B" * 160)),
        ],
    )

    result = SpecialEvidenceStage(provider, input_budget_tokens=600).run(document, [current_item])

    assert result == []
    assert provider.invoke_structured.call_count == 2
    assert [call.kwargs["stage"] for call in provider.invoke_structured.call_args_list] == [
        "special_evidence/1",
        "special_evidence/2",
    ]
