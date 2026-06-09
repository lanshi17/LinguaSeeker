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
