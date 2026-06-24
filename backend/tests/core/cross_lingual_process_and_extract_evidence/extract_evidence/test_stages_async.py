"""Tests for async stage chunk parallelization."""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.catalog import CATALOG_GROUPS
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    DocumentEvidenceMap,
    EvidenceItem,
    EvidenceStatus,
    ExtractionTarget,
    SpecialEvidenceResponse,
    Track,
    TrackDocument,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.catalog_extraction import (
    CatalogExtractionError,
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


def _catalog_task_count(chunk_count: int) -> int:
    # CatalogExtractionStage dispatches every group except `curation` (K),
    # which is cross-paper GDV metadata filled outside the per-document LLM pass.
    return chunk_count * (len(CATALOG_GROUPS) - 1)


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
    assert result.evidence_map.relevant is True


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
        await stage.run_async(_make_document(), _make_evidence_map())
        elapsed = time.monotonic() - start

    assert elapsed < 0.09
    assert mock_provider.ainvoke_structured.await_count == _catalog_task_count(2)


@pytest.mark.asyncio
async def test_catalog_extraction_async_scopes_target_catalog_to_eligible_fields() -> None:
    """Target-scoped async extraction should skip catalog groups with no eligible fields."""
    mock_provider = MagicMock()
    mock_provider.ainvoke_structured = AsyncMock(return_value=[])
    document = TrackDocument(
        document_id="test-doc",
        track=Track.ORIGINAL,
        formatted_text="",
        page_spans=[],
        extraction_target=ExtractionTarget(
            gene_symbol="ABCA3",
            disease_name="ABCA3 deficiency",
        ),
    )

    stage = CatalogExtractionStage(provider=mock_provider)

    with patch(
        "src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.catalog_extraction.build_block_prompt_chunks",
        return_value=[
            MagicMock(
                index=1,
                total=1,
                text="[Block 0 | text | page 1]\nABCA3 deficiency is caused by ABCA3.",
                total_tokens=100,
            ),
        ],
    ):
        await stage.run_async(document, DocumentEvidenceMap(relevant=True))

    # First call is normal catalog extraction; retry may fire a second call
    assert mock_provider.ainvoke_structured.await_count >= 1
    call = mock_provider.ainvoke_structured.call_args_list[0]
    assert call.kwargs["stage"] == "catalog_extraction/high_signal"
    catalog_text = call.kwargs["prompt"].split("EVIDENCE CATALOG", maxsplit=1)[1].split("RULES:", maxsplit=1)[0]
    assert "A.gene_symbol" in catalog_text
    assert "B.disease_diagnosis" in catalog_text
    assert "A.variant_hgvs_c" not in catalog_text
    assert "F.functional_result" not in catalog_text


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
        await stage.run_async(_make_document(), [])
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
    assert result.evidence_map.relevant is True
    assert call_count == 2


@pytest.mark.asyncio
async def test_relevance_scan_raises_when_all_chunks_fail() -> None:
    """When every chunk fails, run_async must raise instead of silently returning relevant=False."""
    mock_provider = MagicMock()
    mock_provider.ainvoke_structured = AsyncMock(side_effect=RuntimeError("Missing credentials"))

    stage = RelevanceScanStage(provider=mock_provider)

    with patch(
        "src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.evidence_map.build_text_prompt_chunks",
        return_value=[
            MagicMock(index=1, total=2, text="chunk1"),
            MagicMock(index=2, total=2, text="chunk2"),
        ],
    ):
        with pytest.raises(RuntimeError, match="Relevance scan failed for all 2 chunks"):
            await stage.run_async(_make_document())


@pytest.mark.asyncio
async def test_catalog_extraction_raises_when_all_chunks_fail() -> None:
    """When every chunk fails, run_async must raise CatalogExtractionError."""
    mock_provider = MagicMock()
    mock_provider.ainvoke_structured = AsyncMock(side_effect=RuntimeError("LLM timeout"))

    stage = CatalogExtractionStage(provider=mock_provider)

    with patch(
        "src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.catalog_extraction.build_block_prompt_chunks",
        return_value=[
            MagicMock(index=1, total=2, text="c1", total_tokens=100),
            MagicMock(index=2, total=2, text="c2", total_tokens=100),
        ],
    ):
        expected_tasks = _catalog_task_count(2)
        with pytest.raises(CatalogExtractionError, match=f"All {expected_tasks} extraction tasks failed"):
            await stage.run_async(_make_document(), _make_evidence_map())


@pytest.mark.asyncio
async def test_catalog_extraction_returns_partial_when_majority_fail() -> None:
    """When >50% chunks fail, run_async logs warning and returns partial results."""
    mock_provider = MagicMock()

    call_count = 0

    async def _partial_fail(**kwargs):  # noqa: ANN003
        nonlocal call_count
        call_count += 1
        if call_count <= 4:
            raise RuntimeError("LLM timeout")
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

    mock_provider.ainvoke_structured = AsyncMock(side_effect=_partial_fail)

    stage = CatalogExtractionStage(provider=mock_provider)

    with patch(
        "src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.catalog_extraction.build_block_prompt_chunks",
        return_value=[
            MagicMock(index=1, total=3, text="c1", total_tokens=100),
            MagicMock(index=2, total=3, text="c2", total_tokens=100),
            MagicMock(index=3, total=3, text="c3", total_tokens=100),
        ],
    ):
        result = await stage.run_async(_make_document(), _make_evidence_map())

    # 4/6 tasks failed (>50%), but successful tasks should still produce results.
    assert len(result) >= 1
    assert call_count == _catalog_task_count(3)


@pytest.mark.asyncio
async def test_catalog_extraction_minority_failure_still_returns() -> None:
    """When <50% chunks fail, run_async returns results from successful chunks."""
    mock_provider = MagicMock()

    call_count = 0

    async def _one_fail(**kwargs):  # noqa: ANN003
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("LLM timeout")
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

    mock_provider.ainvoke_structured = AsyncMock(side_effect=_one_fail)

    stage = CatalogExtractionStage(provider=mock_provider)

    with patch(
        "src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.catalog_extraction.build_block_prompt_chunks",
        return_value=[
            MagicMock(index=1, total=3, text="c1", total_tokens=100),
            MagicMock(index=2, total=3, text="c2", total_tokens=100),
            MagicMock(index=3, total=3, text="c3", total_tokens=100),
        ],
    ):
        result = await stage.run_async(_make_document(), _make_evidence_map())

    # 1/6 tasks failed (<50%), should return results from successful tasks.
    assert len(result) >= 1
    assert call_count == _catalog_task_count(3)
