"""Tests for dual extraction reconcile integration."""

from __future__ import annotations

import pytest

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.api import EvidenceExtractionService
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    DualTrackDocuments,
    EvidenceAlignmentLabel,
    EvidenceExtractionResult,
    EvidenceExtractionStatus,
    EvidenceItem,
    EvidenceStatus,
    ExternalIds,
    ExtractionTarget,
    PageSpan,
    SourceLocation,
    SourcePrecision,
    Track,
    TrackDocument,
)
from src.core.cross_lingual_process_and_extract_evidence.contracts import (
    TranslationAlignmentChunk,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.reconcile.api import (
    CrossTrackReconcileService,
)


class StubEvidenceExtractionService(EvidenceExtractionService):
    """Service double that avoids LLM providers while exercising run_dual()."""

    def __init__(self, results: dict[Track, EvidenceExtractionResult]):
        self._results = results
        self._reconcile_service = CrossTrackReconcileService()

    async def run(
        self,
        document: TrackDocument,
        extraction_profile=None,
        extraction_mode=None,
        enable_review_validation=None,
        enable_target_guard=None,
        enable_source_grounding=None,
        review_reject_policy=None,
    ) -> EvidenceExtractionResult:
        del (
            extraction_profile,
            extraction_mode,
            enable_review_validation,
            enable_target_guard,
            enable_source_grounding,
            review_reject_policy,
        )
        result = self._results[document.track]
        if result.extraction_target is None and document.extraction_target is not None:
            return result.model_copy(update={"extraction_target": document.extraction_target})
        return result


def _item(value: str) -> EvidenceItem:
    return EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.FOUND,
        value=value,
        confidence=0.8,
    )


def _source(snippet: str) -> SourceLocation:
    return SourceLocation(
        span_id="contextual-source-span",
        page=1,
        start_offset=0,
        end_offset=len(snippet),
        context_type="text",
        context_ref="Results",
        text_snippet=snippet,
        source_precision=SourcePrecision.EXACT,
    )


def _relationship_item(value: str, snippet: str) -> EvidenceItem:
    return EvidenceItem(
        field_id="A.gene_disease_relationship",
        category="A",
        field_name="Gene disease relationship",
        status=EvidenceStatus.FOUND,
        value=value,
        confidence=0.7,
        source=_source(snippet),
    )


def _documents(extraction_target: ExtractionTarget | None = None) -> DualTrackDocuments:
    return DualTrackDocuments(
        document_id="doc-dual",
        original=TrackDocument(
            document_id="doc-dual",
            track=Track.ORIGINAL,
            formatted_text="original",
            page_spans=[PageSpan(span_id="o1", page=1, start_offset=0, end_offset=8)],
            external_ids=ExternalIds(pmid="12345678", pmcid="PMC123456"),
            extraction_target=extraction_target,
        ),
        translated=TrackDocument(
            document_id="doc-dual",
            track=Track.TRANSLATED,
            formatted_text="translated",
            page_spans=[PageSpan(span_id="t1", page=1, start_offset=0, end_offset=10)],
            external_ids=ExternalIds(pmid="12345678", pmcid="PMC123456"),
            extraction_target=extraction_target,
        ),
    )


@pytest.mark.asyncio
async def test_run_dual_populates_reconciled_result() -> None:
    service = StubEvidenceExtractionService(
        {
            Track.ORIGINAL: EvidenceExtractionResult(
                status=EvidenceExtractionStatus.COMPLETED,
                document_id="doc-dual",
                track=Track.ORIGINAL,
                evidence_items=[_item("BRCA1")],
            ),
            Track.TRANSLATED: EvidenceExtractionResult(
                status=EvidenceExtractionStatus.COMPLETED,
                document_id="doc-dual",
                track=Track.TRANSLATED,
                evidence_items=[_item("BRCA1")],
            ),
        }
    )

    dual = await service.run_dual(_documents())

    assert dual.reconciled_result is not None
    assert dual.reconciled_result.track == Track.RECONCILED
    assert dual.reconciled_result.evidence_items[0].value == "BRCA1"


@pytest.mark.asyncio
async def test_run_dual_uses_contextual_reconcile_when_target_context_is_available() -> None:
    target = ExtractionTarget(
        gene_symbol="TLR5",
        disease_name="systemic lupus erythematosus",
        clingen_entry_id="clingen_024",
    )
    service = StubEvidenceExtractionService(
        {
            Track.ORIGINAL: EvidenceExtractionResult(
                status=EvidenceExtractionStatus.COMPLETED,
                document_id="doc-dual",
                track=Track.ORIGINAL,
                evidence_items=[
                    _relationship_item(
                        "associated",
                        "Pathogenic variants in TLR5 cause systemic lupus erythematosus "
                        "through altered innate immune signaling.",
                    )
                ],
            ),
            Track.TRANSLATED: EvidenceExtractionResult(
                status=EvidenceExtractionStatus.COMPLETED,
                document_id="doc-dual",
                track=Track.TRANSLATED,
            ),
        }
    )

    dual = await service.run_dual(_documents(extraction_target=target))

    assert dual.reconciled_result is not None
    accepted = dual.reconciled_result.evidence_items[0]
    assert accepted.value == "causative"
    assert "contextual verifier reconcile" in accepted.inference_basis
    assert dual.alignment_records
    assert dual.alignment_records[0].entry_id == "clingen_024"
    assert dual.alignment_records[0].alignment_label == EvidenceAlignmentLabel.MISSING


@pytest.mark.asyncio
async def test_run_dual_english_pivot_maps_english_source_to_original_raw_source() -> None:
    english_text = "Genetic testing suggested interstitial lung disease due to ABCA3 deficiency."
    original_text = "基因检测提示ABCA3缺陷引起的间质性肺病。"
    service = StubEvidenceExtractionService(
        {
            Track.TRANSLATED: EvidenceExtractionResult(
                status=EvidenceExtractionStatus.COMPLETED,
                document_id="doc-dual",
                track=Track.TRANSLATED,
                evidence_items=[
                    EvidenceItem(
                        field_id="B.disease_diagnosis",
                        category="B",
                        field_name="Disease diagnosis",
                        status=EvidenceStatus.FOUND,
                        value="interstitial lung disease due to ABCA3 deficiency",
                        confidence=0.82,
                        source=SourceLocation(
                            span_id="translated-p1",
                            page=1,
                            start_offset=0,
                            end_offset=len(english_text),
                            context_type="text",
                            context_ref="Results",
                            text_snippet=english_text,
                            source_precision=SourcePrecision.EXACT,
                        ),
                    )
                ],
            )
        }
    )
    documents = DualTrackDocuments(
        document_id="doc-dual",
        original=TrackDocument(
            document_id="doc-dual",
            track=Track.ORIGINAL,
            formatted_text=original_text,
            page_spans=[PageSpan(span_id="original-p1", page=1, start_offset=0, end_offset=len(original_text))],
        ),
        translated=TrackDocument(
            document_id="doc-dual",
            track=Track.TRANSLATED,
            formatted_text=english_text,
            page_spans=[PageSpan(span_id="translated-p1", page=1, start_offset=0, end_offset=len(english_text))],
            translation_alignment=[
                TranslationAlignmentChunk(
                    chunk_id="c_0001",
                    original_text=original_text,
                    english_text=english_text,
                    original_start_offset=0,
                    original_end_offset=len(original_text),
                    english_start_offset=0,
                    english_end_offset=len(english_text),
                    page=1,
                    block_index=0,
                )
            ],
        ),
    )

    dual = await service.run_dual(documents, extraction_track_mode="english_pivot")

    assert dual.original_result.evidence_items == []
    assert dual.translated_result.evidence_items[0].source.text_snippet == english_text
    assert dual.translated_result.evidence_items[0].raw_source is not None
    assert dual.translated_result.evidence_items[0].raw_source.text_snippet == original_text
    assert dual.translated_result.evidence_items[0].raw_source.span_id == "original-p1"
    assert dual.reconciled_result is not None
    assert dual.reconciled_result.evidence_items[0].raw_source is not None
    assert dual.reconciled_result.evidence_items[0].raw_source.text_snippet == original_text


@pytest.mark.asyncio
async def test_run_dual_english_pivot_identity_maps_english_original_source() -> None:
    english_text = "Genetic testing suggested MT-TI related hypertrophic cardiomyopathy."
    source = SourceLocation(
        span_id="translated-p1",
        page=1,
        start_offset=0,
        end_offset=len(english_text),
        context_type="text",
        context_ref="Results",
        text_snippet=english_text,
        source_precision=SourcePrecision.EXACT,
    )
    service = StubEvidenceExtractionService(
        {
            Track.TRANSLATED: EvidenceExtractionResult(
                status=EvidenceExtractionStatus.COMPLETED,
                document_id="doc-dual",
                track=Track.TRANSLATED,
                evidence_items=[
                    EvidenceItem(
                        field_id="B.disease_diagnosis",
                        category="B",
                        field_name="Disease diagnosis",
                        status=EvidenceStatus.FOUND,
                        value="hypertrophic cardiomyopathy",
                        confidence=0.82,
                        source=source,
                    )
                ],
            )
        }
    )
    documents = DualTrackDocuments(
        document_id="doc-dual",
        original=TrackDocument(
            document_id="doc-dual",
            track=Track.ORIGINAL,
            formatted_text=english_text,
            page_spans=[PageSpan(span_id="original-p1", page=1, start_offset=0, end_offset=len(english_text))],
        ),
        translated=TrackDocument(
            document_id="doc-dual",
            track=Track.TRANSLATED,
            formatted_text=english_text,
            page_spans=[PageSpan(span_id="translated-p1", page=1, start_offset=0, end_offset=len(english_text))],
            translation_alignment=[],
        ),
    )

    dual = await service.run_dual(documents, extraction_track_mode="english_pivot")

    raw_source = dual.translated_result.evidence_items[0].raw_source
    assert raw_source is not None
    assert raw_source.text_snippet == english_text
    assert raw_source.span_id == "original-p1"
    assert raw_source.context_ref == "Results | translation_traceback:identity"
