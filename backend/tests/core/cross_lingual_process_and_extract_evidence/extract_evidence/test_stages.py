from unittest.mock import MagicMock

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    ContentBlock,
    DocumentEvidenceMap,
    EvidenceItem,
    EvidenceStatus,
    PageSpan,
    QualityReport,
    SourceLocation,
    SourcePrecision,
    Track,
    TrackDocument,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.providers import (
    EvidenceModelTier,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.catalog_extraction import CatalogExtractionStage
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.evidence_map import RelevanceScanStage
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.quality_validation import QualityGateStage
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.source_grounding import SourceGroundingStage
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.special_evidence import SpecialEvidenceStage


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

    assert result.relevant is True
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
            span_id="p1", page=1, start_offset=38, end_offset=41,
            context_type="text", context_ref="",
            text_snippet="GLA", source_precision=SourcePrecision.EXACT,
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
            )
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
            "evidence_field_ids": ["B.disease_diagnosis", "B.case_notes"],
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
            field_id="B.case_notes",
            category="B",
            field_name="Case notes",
            status=EvidenceStatus.FOUND,
            value="retrospective analysis mentioned",
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
            span_id="p1", page=1, start_offset=gla_start, end_offset=gla_start + 3,
            context_type="text", context_ref="",
            text_snippet="GLA", source_precision=SourcePrecision.EXACT,
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
            span_id="p1", page=1, start_offset=38, end_offset=41,
            context_type="text", context_ref="",
            text_snippet="GLA", source_precision=SourcePrecision.EXACT,
        ),
        confidence=0.9,
    )

    stage = QualityGateStage()
    report = stage.run([item], contradictions=[], chains=[], special_records=[])

    assert isinstance(report, QualityReport)
    assert report.passed is True
