"""Tests for parallel search."""

import pytest
from unittest.mock import patch, MagicMock


@pytest.mark.asyncio
async def test_parallel_search_returns_merged_results():
    from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.search_service import search_parallel

    mock_result_1 = MagicMock()
    mock_result_1.success = True
    mock_result_1.items = [{"title": "Paper A", "doi": "10.1/a"}]
    mock_result_1.warnings = []
    mock_result_1.provider = "crossref"

    mock_result_2 = MagicMock()
    mock_result_2.success = True
    mock_result_2.items = [{"title": "Paper B", "doi": "10.1/b"}]
    mock_result_2.warnings = []
    mock_result_2.provider = "openalex"

    with patch(
        "src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.search_service.search_provider",
        side_effect=[mock_result_1, mock_result_2],
    ):
        results = await search_parallel(
            query="BRCA1 mutation",
            plan=[
                {"route": "api", "provider": "crossref"},
                {"route": "api", "provider": "openalex"},
            ],
            concurrency=2,
        )
    assert len(results) == 2
    dois = {r["doi"] for r in results}
    assert "10.1/a" in dois
    assert "10.1/b" in dois
