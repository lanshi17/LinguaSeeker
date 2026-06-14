"""Tests for dual extraction reconcile integration."""
from __future__ import annotations

import pytest

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.api import EvidenceExtractionService
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    DualTrackDocuments,
    EvidenceExtractionResult,
    EvidenceExtractionStatus,
    EvidenceItem,
    EvidenceStatus,
    PageSpan,
    Track,
    TrackDocument,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.reconcile.api import (
    CrossTrackReconcileService,
)


class StubEvidenceExtractionService(EvidenceExtractionService):
    """Service double that avoids LLM providers while exercising run_dual()."""

    def __init__(self, results: dict[Track, EvidenceExtractionResult]):
        self._results = results
        self._reconcile_service = CrossTrackReconcileService()

    async def run(self, document: TrackDocument) -> EvidenceExtractionResult:
        return self._results[document.track]


def _item(value: str) -> EvidenceItem:
    return EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.FOUND,
        value=value,
        confidence=0.8,
    )


def _documents() -> DualTrackDocuments:
    return DualTrackDocuments(
        document_id="doc-dual",
        original=TrackDocument(
            document_id="doc-dual",
            track=Track.ORIGINAL,
            formatted_text="original",
            page_spans=[PageSpan(span_id="o1", page=1, start_offset=0, end_offset=8)],
        ),
        translated=TrackDocument(
            document_id="doc-dual",
            track=Track.TRANSLATED,
            formatted_text="translated",
            page_spans=[PageSpan(span_id="t1", page=1, start_offset=0, end_offset=10)],
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
