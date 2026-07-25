"""Tests for async workflow execution."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.evidence_extraction.contracts import (
    DocumentEvidenceMap,
    EvidenceItem,
    EvidenceExtractionStatus,
    EvidenceStatus,
    PrimaryBroadExtractionResponse,
    SourceLocation,
    SpecialEvidenceResponse,
    Track,
    TrackDocument,
)
from src.core.evidence_extraction.workflow import (
    EvidenceExtractionWorkflow,
)


def _make_document() -> TrackDocument:
    return TrackDocument(
        document_id="test-doc",
        track=Track.ORIGINAL,
        formatted_text="Some text about BRCA1 variant.",
        page_spans=[],
    )


def _legacy_stage_response(stage: str) -> object:
    if stage.startswith("catalog_extraction"):
        return [
            EvidenceItem(
                field_id="A.gene_symbol",
                category="A",
                field_name="Gene symbol",
                status=EvidenceStatus.FOUND,
                value="BRCA1",
                confidence=0.9,
                raw_source=SourceLocation(
                    block_index=0,
                    context_type="text",
                    context_ref="",
                    text_snippet="BRCA1",
                ),
            )
        ]
    if stage.startswith("special_evidence"):
        return SpecialEvidenceResponse()
    if stage.startswith("clinical_context"):
        return []
    return DocumentEvidenceMap(relevant=True, disease_terms=["cancer"])


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
async def test_workflow_run_async_legacy_completed() -> None:
    """run_async legacy rollback completes the catalog pipeline for a relevant document."""
    mock_provider = MagicMock()

    async def _relevant(**kwargs):  # noqa: ANN003
        return _legacy_stage_response(kwargs["stage"])

    mock_provider.ainvoke_structured = AsyncMock(side_effect=_relevant)

    workflow = EvidenceExtractionWorkflow(provider=mock_provider, extraction_mode="catalog")

    state = await workflow.run_async(_make_document())

    assert state.status == EvidenceExtractionStatus.COMPLETED
    assert state.evidence_map is not None
    assert state.evidence_map.relevant is True
    assert not any(
        call.kwargs["stage"] == "primary_broad_extraction" for call in mock_provider.ainvoke_structured.call_args_list
    )


@pytest.mark.asyncio
async def test_workflow_run_async_default_uses_primary_broad_extraction() -> None:
    """run_async default (business b8) uses primary_broad_extraction, not catalog."""
    mock_provider = MagicMock()

    async def _b8_response(**kwargs):  # noqa: ANN003
        if kwargs["stage"] == "primary_broad_extraction":
            return PrimaryBroadExtractionResponse()
        return DocumentEvidenceMap(relevant=True, disease_terms=["cancer"])

    mock_provider.ainvoke_structured = AsyncMock(side_effect=_b8_response)

    workflow = EvidenceExtractionWorkflow(provider=mock_provider)

    state = await workflow.run_async(_make_document())

    assert state.status == EvidenceExtractionStatus.COMPLETED
    assert any(
        call.kwargs["stage"] == "primary_broad_extraction" for call in mock_provider.ainvoke_structured.call_args_list
    )
    assert not any(
        call.kwargs["stage"].startswith("catalog_extraction")
        for call in mock_provider.ainvoke_structured.call_args_list
    )


@pytest.mark.asyncio
async def test_workflow_run_async_is_faster_than_sequential() -> None:
    """run_async with multi-chunk should be faster than sequential run."""
    import time
    import asyncio

    mock_provider = MagicMock()

    async def _slow(**kwargs):  # noqa: ANN003
        await asyncio.sleep(0.05)
        response = _legacy_stage_response(kwargs["stage"])
        if isinstance(response, DocumentEvidenceMap):
            return DocumentEvidenceMap(relevant=True, disease_terms=["d"])
        return response

    mock_provider.ainvoke_structured = AsyncMock(side_effect=_slow)

    workflow = EvidenceExtractionWorkflow(provider=mock_provider, extraction_mode="catalog")
    doc = _make_document()

    # Patch build_text_prompt_chunks to return 3 chunks
    from unittest.mock import patch

    chunks = [
        MagicMock(index=1, total=3, text="c1"),
        MagicMock(index=2, total=3, text="c2"),
        MagicMock(index=3, total=3, text="c3"),
    ]

    with patch(
        "src.core.evidence_extraction.stages.evidence_map.build_text_prompt_chunks",
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
