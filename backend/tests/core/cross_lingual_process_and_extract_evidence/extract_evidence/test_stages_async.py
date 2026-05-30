"""Tests for async stage chunk parallelization."""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    DocumentEvidenceMap,
    EvidenceItem,
    EvidenceStatus,
    SpecialEvidenceResponse,
    Track,
    TrackDocument,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.catalog_extraction import (
    CatalogExtractionStage,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.evidence_map import (
    RelevanceScanStage,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.special_evidence import (
    SpecialEvidenceStage,
)


def _make_document() -> TrackDocument:
    return TrackDocument(
        document_id="test-doc",
        track=Track.ORIGINAL,
        formatted_text="word " * 20000,
        page_spans=[],
    )


def _make_evidence_map() -> DocumentEvidenceMap:
    return DocumentEvidenceMap(relevant=True, disease_terms=["cancer"], gene_terms=["BRCA1"])


@pytest.mark.asyncio
async def test_relevance_scan_async_runs_chunks_concurrently() -> None:
    """run_async should invoke all chunks concurrently, not sequentially."""
    mock_provider = MagicMock()

    async def _slow_ainvoke(**kwargs):  # noqa: ANN003
        await asyncio.sleep(0.05)
        return DocumentEvidenceMap(relevant=True, disease_terms=["d"])

    mock_provider.ainvoke_structured = AsyncMock(side_effect=_slow_ainvoke)

    stage = RelevanceScanStage(provider=mock_provider)

    with patch(
        "src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.evidence_map.build_text_prompt_chunks",
        return_value=[
            MagicMock(index=1, total=2, text="chunk1"),
            MagicMock(index=2, total=2, text="chunk2"),
        ],
    ):
        start = time.monotonic()
        result = await stage.run_async(_make_document())
        elapsed = time.monotonic() - start

    assert elapsed < 0.09
    assert mock_provider.ainvoke_structured.await_count == 2
    assert result.relevant is True


@pytest.mark.asyncio
async def test_catalog_extraction_async_runs_chunks_concurrently() -> None:
    """CatalogExtractionStage.run_async should invoke all chunks concurrently."""
    mock_provider = MagicMock()

    async def _slow_ainvoke(**kwargs):  # noqa: ANN003
        await asyncio.sleep(0.05)
        return [
            EvidenceItem(
                field_id="F1",
                category="cat",
                field_name="fn",
                status=EvidenceStatus.FOUND,
                value="v",
                confidence=0.9,
            )
        ]

    mock_provider.ainvoke_structured = AsyncMock(side_effect=_slow_ainvoke)

    stage = CatalogExtractionStage(provider=mock_provider)

    with patch(
        "src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.catalog_extraction.build_block_prompt_chunks",
        return_value=[
            MagicMock(index=1, total=2, text="c1", total_tokens=100),
            MagicMock(index=2, total=2, text="c2", total_tokens=100),
        ],
    ):
        start = time.monotonic()
        result = await stage.run_async(_make_document(), _make_evidence_map())
        elapsed = time.monotonic() - start

    assert elapsed < 0.09
    assert mock_provider.ainvoke_structured.await_count == 2


@pytest.mark.asyncio
async def test_special_evidence_async_runs_chunks_concurrently() -> None:
    """SpecialEvidenceStage.run_async should invoke all chunks concurrently."""
    mock_provider = MagicMock()

    async def _slow_ainvoke(**kwargs):  # noqa: ANN003
        await asyncio.sleep(0.05)
        return SpecialEvidenceResponse(records=[])

    mock_provider.ainvoke_structured = AsyncMock(side_effect=_slow_ainvoke)

    stage = SpecialEvidenceStage(provider=mock_provider)

    with patch(
        "src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.special_evidence.build_block_prompt_chunks",
        return_value=[
            MagicMock(index=1, total=2, text="c1", total_tokens=100),
            MagicMock(index=2, total=2, text="c2", total_tokens=100),
        ],
    ):
        start = time.monotonic()
        result = await stage.run_async(_make_document(), [])
        elapsed = time.monotonic() - start

    assert elapsed < 0.09
    assert mock_provider.ainvoke_structured.await_count == 2


@pytest.mark.asyncio
async def test_stage_async_survives_chunk_failure() -> None:
    """A failed chunk should be logged and skipped, not abort the stage."""
    mock_provider = MagicMock()

    call_count = 0

    async def _partial_fail(**kwargs):  # noqa: ANN003
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("simulated LLM failure")
        return DocumentEvidenceMap(relevant=True, disease_terms=["d"])

    mock_provider.ainvoke_structured = AsyncMock(side_effect=_partial_fail)

    stage = RelevanceScanStage(provider=mock_provider)

    with patch(
        "src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.evidence_map.build_text_prompt_chunks",
        return_value=[
            MagicMock(index=1, total=2, text="chunk1"),
            MagicMock(index=2, total=2, text="chunk2"),
        ],
    ):
        result = await stage.run_async(_make_document())

    # Should still return a merged result from the successful chunk
    assert result.relevant is True
    assert call_count == 2
