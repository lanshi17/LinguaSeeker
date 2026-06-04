"""Integration tests for the refactored three-phase workflow."""

import pytest
from unittest.mock import AsyncMock, patch


class TestMergeAndDedupe:
    def test_dedup_by_doi(self):
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow import _merge_and_dedupe
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.web_search import SearchLink

        api_items = [{"doi": "10.1234/test", "title": "Paper A", "_source_provider": "crossref"}]
        firecrawl_links = [SearchLink(url="https://example.com/paper", doi="10.1234/test")]

        merged = _merge_and_dedupe(api_items, firecrawl_links)
        assert len(merged) == 1
        assert merged[0]["_candidate_type"] == "api"

    def test_dedup_by_url(self):
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow import _merge_and_dedupe
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.web_search import SearchLink

        api_items = [{"url": "https://example.com/paper.pdf", "_source_provider": "crossref"}]
        firecrawl_links = [SearchLink(url="https://example.com/paper.pdf")]

        merged = _merge_and_dedupe(api_items, firecrawl_links)
        assert len(merged) == 1

    def test_merges_distinct_items(self):
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow import _merge_and_dedupe
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.web_search import SearchLink

        api_items = [{"doi": "10.1234/a", "title": "Paper A", "_source_provider": "crossref"}]
        firecrawl_links = [SearchLink(url="https://example.com/different-paper.pdf")]

        merged = _merge_and_dedupe(api_items, firecrawl_links)
        assert len(merged) == 2

    def test_empty_inputs(self):
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow import _merge_and_dedupe

        merged = _merge_and_dedupe([], [])
        assert merged == []

    def test_dedup_by_title(self):
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow import _merge_and_dedupe

        api_items = [
            {"doi": "10.1111/a", "title": "BRCA1 Case Report", "_source_provider": "crossref"},
            {"doi": "10.1111/b", "title": "BRCA1 case report", "_source_provider": "unpaywall"},
        ]

        merged = _merge_and_dedupe(api_items, [])
        assert len(merged) == 1

    def test_dedup_with_list_title(self):
        """Crossref returns title as a list — must not crash."""
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow import _merge_and_dedupe

        api_items = [
            {"doi": "10.1111/a", "title": ["BRCA1 Case Report"], "_source_provider": "crossref"},
            {"doi": "10.1111/b", "title": "BRCA1 case report", "_source_provider": "unpaywall"},
        ]

        merged = _merge_and_dedupe(api_items, [])
        assert len(merged) == 1

    def test_dedup_with_list_url(self):
        """Some providers return URL as a list."""
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow import _merge_and_dedupe

        api_items = [
            {"url": ["https://example.com/paper.pdf"], "_source_provider": "crossref"},
            {"url": "https://example.com/paper.pdf", "_source_provider": "unpaywall"},
        ]

        merged = _merge_and_dedupe(api_items, [])
        assert len(merged) == 1

    def test_coerce_str_extracts_from_list(self):
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow import _coerce_str

        assert _coerce_str(["hello", "world"]) == "hello"
        assert _coerce_str("direct") == "direct"
        assert _coerce_str(None) == ""
        assert _coerce_str([]) == ""
        assert _coerce_str({"value": "nested"}) == "nested"


class TestAcquireLinksApi:
    @pytest.mark.asyncio
    async def test_parallel_search_returns_items(self):
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow import _acquire_links_api
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.contracts import (
            OnlineAcquisitionGatewayResult,
        )

        mock_result = OnlineAcquisitionGatewayResult(
            provider="crossref",
            success=True,
            items=[{"title": "Test Paper", "doi": "10.1234/test"}],
            warnings=[],
            raw=None,
            meta=None,
            source_trace=[],
        )

        with patch(
            "src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow.search_provider",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            items = await _acquire_links_api(
                query="test",
                identifiers={"doi": "10.1234/test"},
                limit=10,
            )

        assert len(items) > 0
        assert items[0].get("_source_provider") == "crossref"

    @pytest.mark.asyncio
    async def test_provider_failure_does_not_crash(self):
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow import _acquire_links_api

        with patch(
            "src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow.search_provider",
            new_callable=AsyncMock,
            side_effect=Exception("provider down"),
        ):
            items = await _acquire_links_api(
                query="test",
                identifiers={},
                limit=10,
            )

        assert items == []


class TestDownloadCandidates:
    @pytest.mark.asyncio
    async def test_download_doi_route(self, tmp_path):
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow import _download_candidates
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.contracts import (
            OnlineAcquisitionGatewayResult,
        )

        candidates = [{"doi": "10.1234/test", "title": "Test Paper", "_source_provider": "crossref"}]

        mock_unpaywall = OnlineAcquisitionGatewayResult(
            provider="unpaywall",
            success=True,
            items=[{"pmcid": "PMC123"}],
            downloads=[{"pdf_url": "https://example.com/paper.pdf"}],
            warnings=[],
            raw=None,
            meta=None,
            source_trace=[],
        )

        with patch(
            "src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow.search_provider",
            new_callable=AsyncMock,
            return_value=mock_unpaywall,
        ), patch(
            "src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow.download_file_from_url",
            new_callable=AsyncMock,
            return_value=(str(tmp_path / "paper.pdf"), "https://example.com/paper.pdf", []),
        ):
            # Create the file so it passes validation
            (tmp_path / "paper.pdf").write_bytes(b"%PDF-1.4 fake")
            results = await _download_candidates(candidates, str(tmp_path))

        assert len(results) == 1
        assert results[0].source == "unpaywall"
        assert results[0].doi == "10.1234/test"

    @pytest.mark.asyncio
    async def test_download_doi_with_list_title(self, tmp_path):
        """Crossref returns title as list — download must still trigger."""
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow import _download_candidates
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.contracts import (
            OnlineAcquisitionGatewayResult,
        )

        candidates = [{"doi": "10.1234/test", "title": ["Paper Title"], "_source_provider": "crossref"}]

        mock_unpaywall = OnlineAcquisitionGatewayResult(
            provider="unpaywall",
            success=True,
            items=[],
            downloads=[{"pdf_url": "https://example.com/paper.pdf"}],
            warnings=[],
            raw=None,
            meta=None,
            source_trace=[],
        )

        search_called = False

        async def mock_search(**kwargs):
            nonlocal search_called
            search_called = True
            return mock_unpaywall

        with patch(
            "src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow.search_provider",
            new_callable=AsyncMock,
            side_effect=mock_search,
        ), patch(
            "src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow.download_file_from_url",
            new_callable=AsyncMock,
            return_value=(str(tmp_path / "paper.pdf"), "https://example.com/paper.pdf", []),
        ):
            (tmp_path / "paper.pdf").write_bytes(b"%PDF-1.4 fake")
            results = await _download_candidates(candidates, str(tmp_path))

        assert search_called, "search_provider must be called even with list-shaped title"
        assert len(results) == 1
        assert results[0].source == "unpaywall"

    @pytest.mark.asyncio
    async def test_download_empty_candidates(self, tmp_path):
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow import _download_candidates

        results = await _download_candidates([], str(tmp_path))
        assert results == []

    @pytest.mark.asyncio
    async def test_download_failure_returns_empty(self, tmp_path):
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow import _download_candidates

        candidates = [{"url": "https://example.com/bad.pdf", "title": "Bad Paper"}]

        with patch(
            "src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow.download_file_from_url",
            new_callable=AsyncMock,
            return_value=(None, None, ["download_error"]),
        ):
            results = await _download_candidates(candidates, str(tmp_path))

        assert results == []
