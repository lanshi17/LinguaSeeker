"""Tests for async workflow execution."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    DocumentEvidenceMap,
    EvidenceExtractionStatus,
    PrimaryBroadExtractionResponse,
    Track,
    TrackDocument,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.workflow import (
    EvidenceExtractionWorkflow,
)


def _make_document() -> TrackDocument:
    return TrackDocument(
        document_id="test-doc",
        track=Track.ORIGINAL,
        formatted_text="Some text about BRCA1 variant.",
        page_spans=[],
    )


@pytest.mark.asyncio
async def test_workflow_run_async_not_relevant() -> None:
    """run_async should return NOT_RELEVANT state when document is not relevant."""
    mock_provider = MagicMock()

    async def _not_relevant(**kwargs):  # noqa: ANN003
        return DocumentEvidenceMap(relevant=False)

    mock_provider.ainvoke_structured = AsyncMock(side_effect=_not_relevant)

    workflow = EvidenceExtractionWorkflow(provider=mock_provider)

    state = await workflow.run_async(_make_document())

    assert state.status == EvidenceExtractionStatus.NOT_RELEVANT
    assert state.evidence_map is not None
    assert state.evidence_map.relevant is False


@pytest.mark.asyncio
async def test_workflow_run_async_completed() -> None:
    """run_async should complete full pipeline for a relevant document."""
    mock_provider = MagicMock()

    async def _relevant(**kwargs):  # noqa: ANN003
        if kwargs["stage"] == "primary_broad_extraction":
            return PrimaryBroadExtractionResponse()
        return DocumentEvidenceMap(relevant=True, disease_terms=["cancer"])

    mock_provider.ainvoke_structured = AsyncMock(side_effect=_relevant)

    workflow = EvidenceExtractionWorkflow(provider=mock_provider)

    state = await workflow.run_async(_make_document())

    assert state.status == EvidenceExtractionStatus.COMPLETED
    assert state.evidence_map is not None
    assert state.evidence_map.relevant is True


@pytest.mark.asyncio
async def test_workflow_run_async_is_faster_than_sequential() -> None:
    """run_async with multi-chunk should be faster than sequential run."""
    import time
    import asyncio

    mock_provider = MagicMock()

    async def _slow(**kwargs):  # noqa: ANN003
        await asyncio.sleep(0.05)
        if kwargs["stage"] == "primary_broad_extraction":
            return PrimaryBroadExtractionResponse()
        return DocumentEvidenceMap(relevant=True, disease_terms=["d"])

    mock_provider.ainvoke_structured = AsyncMock(side_effect=_slow)

    workflow = EvidenceExtractionWorkflow(provider=mock_provider)
    doc = _make_document()

    # Patch build_text_prompt_chunks to return 3 chunks
    from unittest.mock import patch

    chunks = [
        MagicMock(index=1, total=3, text="c1"),
        MagicMock(index=2, total=3, text="c2"),
        MagicMock(index=3, total=3, text="c3"),
    ]

    with patch(
        "src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.evidence_map.build_text_prompt_chunks",
        return_value=chunks,
    ):
        start = time.monotonic()
        state = await workflow.run_async(doc)
        elapsed = time.monotonic() - start

    # 3 chunks × 50ms concurrent ≈ 50-80ms for relevance_scan alone.
    # Full pipeline adds catalog_extraction + special_evidence (1 call each) ≈ +100ms.
    # Sequential would be ~350ms+; concurrent should be under 250ms.
    assert elapsed < 0.25
    assert state.status == EvidenceExtractionStatus.NOT_RELEVANT or state.evidence_map is not None
