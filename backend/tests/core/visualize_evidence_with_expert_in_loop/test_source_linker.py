"""Tests for SourceLinker read path."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


@pytest.mark.asyncio
async def test_get_track_span_loads_canonical_then_fetches_run() -> None:
    """SourceLinker.get_track_span loads canonical item first, then fetches the best run via current_best_run_evidence_id."""
    from src.core.visualize_evidence_with_expert_in_loop.source_linker import SourceLinker

    session = MagicMock()
    canonical_id = uuid4()
    best_run_id = uuid4()

    # Mock canonical item with current_best_run_evidence_id
    mock_canonical = MagicMock()
    mock_canonical.current_best_run_evidence_id = best_run_id

    # Mock the best run evidence item
    mock_run = MagicMock()
    mock_run.source_span = {"text_snippet": "test snippet", "start_offset": 0, "end_offset": 4}
    mock_run.track = "original"

    # First execute returns canonical, second returns run
    canonical_result = MagicMock()
    canonical_result.scalar_one_or_none.return_value = mock_canonical
    run_result = MagicMock()
    run_result.scalar_one_or_none.return_value = mock_run
    session.execute = AsyncMock(side_effect=[canonical_result, run_result])

    linker = SourceLinker(session)
    span = await linker.get_track_span(canonical_evidence_id=canonical_id, track="original")

    assert span is not None
    assert session.execute.await_count == 2


@pytest.mark.asyncio
async def test_get_track_span_returns_none_when_canonical_not_found() -> None:
    """SourceLinker.get_track_span returns None when canonical item doesn't exist."""
    from src.core.visualize_evidence_with_expert_in_loop.source_linker import SourceLinker

    session = MagicMock()
    canonical_result = MagicMock()
    canonical_result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=canonical_result)

    linker = SourceLinker(session)
    span = await linker.get_track_span(canonical_evidence_id=uuid4(), track="original")

    assert span is None
    assert session.execute.await_count == 1  # Only canonical query, no run query


@pytest.mark.asyncio
async def test_get_track_span_falls_back_when_best_track_mismatches() -> None:
    """When best run is 'original' but track='translated' is requested, must fall back to identity-tuple lookup."""
    from src.core.visualize_evidence_with_expert_in_loop.source_linker import SourceLinker

    session = MagicMock()
    canonical_id = uuid4()
    doc_id = uuid4()

    # Canonical item with identity fields
    mock_canonical = MagicMock()
    mock_canonical.current_best_run_evidence_id = uuid4()  # best run is original
    mock_canonical.source_document_id = doc_id
    mock_canonical.field_id = "A.gene_symbol"
    mock_canonical.position_hash = "abc123"
    mock_canonical.entity_scope_hash = "def456"

    # Best run item — track is "original", NOT "translated"
    mock_best_run = MagicMock()
    mock_best_run.track = "original"
    mock_best_run.source_span = {"text_snippet": "original text"}

    # Fallback run item — track is "translated"
    mock_translated_run = MagicMock()
    mock_translated_run.track = "translated"
    mock_translated_run.source_span = {"text_snippet": "translated text"}

    canonical_result = MagicMock()
    canonical_result.scalar_one_or_none.return_value = mock_canonical
    best_run_result = MagicMock()
    best_run_result.scalar_one_or_none.return_value = mock_best_run
    fallback_result = MagicMock()
    fallback_result.scalar_one_or_none.return_value = mock_translated_run

    # 3 queries: canonical, best run (track mismatch), fallback by identity tuple
    session.execute = AsyncMock(side_effect=[canonical_result, best_run_result, fallback_result])

    linker = SourceLinker(session)
    span = await linker.get_track_span(canonical_evidence_id=canonical_id, track="translated")

    assert span is not None
    assert span.block_text == "translated text"
    assert session.execute.await_count == 3  # canonical + best (mismatch) + fallback


@pytest.mark.asyncio
async def test_get_bilingual_span_returns_different_tracks() -> None:
    """get_bilingual_span must return different run items for original vs translated."""
    from src.core.visualize_evidence_with_expert_in_loop.source_linker import SourceLinker

    session = MagicMock()
    canonical_id = uuid4()
    doc_id = uuid4()

    mock_canonical = MagicMock()
    mock_canonical.current_best_run_evidence_id = uuid4()
    mock_canonical.source_document_id = doc_id
    mock_canonical.field_id = "A.gene_symbol"
    mock_canonical.position_hash = "abc123"
    mock_canonical.entity_scope_hash = "def456"

    # Best run is "original"
    mock_original = MagicMock()
    mock_original.track = "original"
    mock_original.source_span = {"text_snippet": "BRCA1 detected"}

    # Translated run (found via fallback)
    mock_translated = MagicMock()
    mock_translated.track = "translated"
    mock_translated.source_span = {"text_snippet": "检测到 BRCA1"}

    canonical_result = MagicMock()
    canonical_result.scalar_one_or_none.return_value = mock_canonical
    original_best = MagicMock()
    original_best.scalar_one_or_none.return_value = mock_original
    translated_fallback = MagicMock()
    translated_fallback.scalar_one_or_none.return_value = mock_translated

    # Call 1 (original): canonical + best_run(match) = 2 queries
    # Call 2 (translated): canonical + best_run(mismatch) + fallback = 3 queries
    session.execute = AsyncMock(side_effect=[
        canonical_result, original_best,   # get_track_span("original")
        canonical_result, original_best, translated_fallback,  # get_track_span("translated")
    ])

    linker = SourceLinker(session)
    bilingual = await linker.get_bilingual_span(canonical_evidence_id=canonical_id)

    assert bilingual.original_track is not None
    assert bilingual.translated_track is not None
    assert bilingual.original_track.block_text == "BRCA1 detected"
    assert bilingual.translated_track.block_text == "检测到 BRCA1"
