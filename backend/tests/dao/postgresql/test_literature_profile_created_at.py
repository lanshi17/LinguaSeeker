"""Tests for created_at exposure in literature profile search."""

from __future__ import annotations

from unittest.mock import MagicMock, AsyncMock
from datetime import datetime, timezone

import pytest


@pytest.mark.asyncio
async def test_search_result_dict_contains_created_at():
    """LiteratureProfileRepository.search() result dicts must include created_at."""
    from src.dao.postgresql.literature_profile_repo import LiteratureProfileRepository

    # Build a mock row that mimics a LiteratureProfile ORM object.
    mock_row = MagicMock()
    mock_row.literature_profile_id = "00000000-0000-0000-0000-000000000001"
    mock_row.source_document_id = "00000000-0000-0000-0000-000000000002"
    mock_row.pmid = "12345"
    mock_row.doi = "10.1000/test"
    mock_row.title = "Test Paper"
    mock_row.journal = "Test Journal"
    mock_row.publication_year = 2026
    mock_row.review_status = "provisional"
    mock_row.overall_confidence = None
    mock_row.total_evidence_fields = 1
    mock_row.found_count = 1
    mock_row.evidence_groups = []
    mock_row.created_at = datetime(2026, 6, 10, 12, 0, 0, tzinfo=timezone.utc)

    # Mock session: count query returns 1, data query returns [mock_row].
    mock_session = AsyncMock()

    count_result = MagicMock()
    count_result.scalar_one.return_value = 1

    data_result = MagicMock()
    data_result.scalars.return_value.all.return_value = [mock_row]

    call_count = 0

    async def mock_execute(stmt):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return count_result
        return data_result

    mock_session.execute = mock_execute

    repo = LiteratureProfileRepository(mock_session)
    items, total = await repo.search(page=1, page_size=50)

    assert total == 1
    assert len(items) == 1
    assert "created_at" in items[0]
    assert items[0]["created_at"] == "2026-06-10T12:00:00+00:00"
