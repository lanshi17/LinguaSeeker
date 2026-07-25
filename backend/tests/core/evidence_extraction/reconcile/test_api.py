"""Tests for the cross-track reconcile service facade."""

from __future__ import annotations

from src.core.evidence_extraction.contracts import (
    EvidenceExtractionResult,
    EvidenceExtractionStatus,
    EvidenceItem,
    EvidenceStatus,
    ExtractionTarget,
    SourceLocation,
    SourcePrecision,
    Track,
)
from src.core.evidence_extraction.reconcile.api import (
    CrossTrackReconcileService,
)
from src.core.standardize_entities_and_align_knowledge.context_pack.contracts import (
    DiseaseContext,
    GeneContext,
    TargetContextPack,
)


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
        span_id="source-span",
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


def _context() -> TargetContextPack:
    return TargetContextPack(
        entry_id="clingen_024",
        gene=GeneContext(symbol="TLR5", hgnc_id=None, aliases=("TLR5",)),
        disease=DiseaseContext(
            label="systemic lupus erythematosus",
            mondo_id=None,
            aliases=("systemic lupus erythematosus",),
            ancestor_labels=(),
        ),
        moi="AD",
        source_pmid=None,
        source_pmc=None,
    )


def test_reconcile_service_returns_reconciled_extraction_result() -> None:
    target = ExtractionTarget(gene_symbol="brca1", disease_name="Breast cancer")
    original = EvidenceExtractionResult(
        status=EvidenceExtractionStatus.COMPLETED,
        document_id="doc-service",
        track=Track.ORIGINAL,
        evidence_items=[_item("BRCA1")],
        extraction_target=target,
    )
    translated = EvidenceExtractionResult(
        status=EvidenceExtractionStatus.COMPLETED,
        document_id="doc-service",
        track=Track.TRANSLATED,
        evidence_items=[_item("BRCA1")],
    )

    result = CrossTrackReconcileService().run(original, translated)

    assert result.track == Track.RECONCILED
    assert result.document_id == "doc-service"
    assert result.extraction_target == target
    assert result.evidence_items[0].value == "BRCA1"


def test_reconcile_service_uses_contextual_verifier_when_context_pack_is_supplied() -> None:
    original = EvidenceExtractionResult(
        status=EvidenceExtractionStatus.COMPLETED,
        document_id="doc-service",
        track=Track.ORIGINAL,
        evidence_items=[
            _relationship_item(
                "associated",
                "Pathogenic variants in TLR5 cause systemic lupus erythematosus "
                "through altered innate immune signaling.",
            )
        ],
    )
    translated = EvidenceExtractionResult(
        status=EvidenceExtractionStatus.COMPLETED,
        document_id="doc-service",
        track=Track.TRANSLATED,
    )

    result = CrossTrackReconcileService().run(original, translated, context_pack=_context())

    assert result.evidence_items[0].value == "causative"
    assert "contextual verifier reconcile" in result.evidence_items[0].inference_basis
