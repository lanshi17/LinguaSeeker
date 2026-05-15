from unittest.mock import MagicMock

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    DocumentEvidenceMap,
    EvidenceChain,
    EvidenceExtractionState,
    EvidenceExtractionStatus,
    EvidenceItem,
    EvidenceStatus,
    PageSpan,
    QualityReport,
    SourceLocation,
    SourcePrecision,
    SpecialEvidenceRecord,
    Track,
    TrackDocument,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.providers import (
    EvidenceModelTier,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.catalog_extraction import CatalogExtractionStage
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.evidence_map import EvidenceMapStage
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.quality_validation import QualityValidationStage
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.source_grounding import SourceGroundingStage
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.special_evidence import SpecialEvidenceStage


def _doc() -> TrackDocument:
    return TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text="Patient 1 had Fabry disease and carried a hemizygous GLA c.1000G>A variant.",
        page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=78)],
    )


def test_evidence_map_stage_calls_fast_tier():
    provider = MagicMock()
    emap = DocumentEvidenceMap(relevant=True, gene_terms=["GLA"])
    provider.invoke_structured.return_value = emap

    stage = EvidenceMapStage(provider)
    result = stage.run(_doc())

    assert result.relevant is True
    provider.invoke_structured.assert_called_once()
    call_kwargs = provider.invoke_structured.call_args
    assert call_kwargs.kwargs["tier"] == EvidenceModelTier.FAST


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
    call_kwargs = provider.invoke_structured.call_args
    assert call_kwargs.kwargs["tier"] == EvidenceModelTier.STRONG


def test_special_evidence_stage_calls_strong_tier():
    provider = MagicMock()
    provider.invoke_structured.return_value = []

    stage = SpecialEvidenceStage(provider)
    result = stage.run(_doc(), [])

    assert result == []
    call_kwargs = provider.invoke_structured.call_args
    assert call_kwargs.kwargs["tier"] == EvidenceModelTier.STRONG


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
    result = stage.run(_doc(), [item])

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

    stage = QualityValidationStage()
    report = stage.run([item], contradictions=[])

    assert isinstance(report, QualityReport)
    assert report.passed is True
