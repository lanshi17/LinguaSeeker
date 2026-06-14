"""Tests for the cross-track reconcile service facade."""
from __future__ import annotations

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceExtractionResult,
    EvidenceExtractionStatus,
    EvidenceItem,
    EvidenceStatus,
    ExtractionTarget,
    Track,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.reconcile.api import (
    CrossTrackReconcileService,
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
