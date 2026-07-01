"""Tests for web search adapter interface."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.web_search.adapter import (
    SearchLink,
    WebSearchAdapter,
    WebSearchResult,
)


class TestSearchLink:
    def test_search_link_creation(self):
        link = SearchLink(url="https://example.com/paper.pdf", source="test", title="Test Paper")
        assert link.url == "https://example.com/paper.pdf"
        assert link.source == "test"
        assert link.title == "Test Paper"

    def test_search_link_optional_fields(self):
        link = SearchLink(url="https://example.com/paper.pdf")
        assert link.source is None
        assert link.title is None


class TestWebSearchResult:
    def test_web_search_result_creation(self):
        links = [SearchLink(url="https://example.com/1.pdf")]
        result = WebSearchResult(links=links, query="test query", provider="test")
        assert len(result.links) == 1
        assert result.query == "test query"
        assert result.warnings == []


class TestWebSearchAdapter:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            WebSearchAdapter(api_key="test")

    def test_subclass_must_implement(self):
        class IncompleteAdapter(WebSearchAdapter):
            pass

        with pytest.raises(TypeError):
            IncompleteAdapter(api_key="test")


class TestFirecrawlAdapter:
    def test_init_requires_api_key(self):
        """Adapter stores config."""
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.web_search.firecrawl_adapter import (
            FirecrawlAdapter,
        )

        adapter = FirecrawlAdapter(
            api_key="fc-test-key", base_url="https://api.firecrawl.dev", timeout=10, max_results=5
        )
        assert adapter.api_key == "fc-test-key"
        assert adapter.max_results == 5

    @pytest.mark.asyncio
    async def test_search_returns_links_from_dict(self):
        """search() handles dict response (direct API calls)."""
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.web_search.firecrawl_adapter import (
            FirecrawlAdapter,
        )

        adapter = FirecrawlAdapter(api_key="fc-test-key")

        mock_search_result = {
            "web": [
                {"url": "https://journal.com/article/1", "title": "Paper One"},
                {"url": "https://journal.com/article/2", "title": "Paper Two"},
            ]
        }

        with patch.object(adapter, "_client", new_callable=MagicMock) as mock_client:
            mock_client.search = AsyncMock(return_value=mock_search_result)
            result = await adapter.search("BRCA1 case report")

        assert result.provider == "firecrawl"
        assert len(result.links) == 2
        assert result.links[0].url == "https://journal.com/article/1"

    @pytest.mark.asyncio
    async def test_search_handles_pydantic_response(self):
        """search() handles Pydantic model response from SDK."""
        from pydantic import BaseModel
        from typing import List as ListType

        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.web_search.firecrawl_adapter import (
            FirecrawlAdapter,
        )

        class WebResult(BaseModel):
            url: str
            title: str = ""

        class SearchResponse(BaseModel):
            web: ListType[WebResult] = []

        adapter = FirecrawlAdapter(api_key="fc-test-key")
        mock_response = SearchResponse(
            web=[
                WebResult(url="https://journal.com/article/1", title="Paper One"),
            ]
        )

        with patch.object(adapter, "_client", new_callable=MagicMock) as mock_client:
            mock_client.search = AsyncMock(return_value=mock_response)
            result = await adapter.search("test query")

        assert len(result.links) == 1
        assert result.links[0].url == "https://journal.com/article/1"

    @pytest.mark.asyncio
    async def test_search_handles_empty_results(self):
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.web_search.firecrawl_adapter import (
            FirecrawlAdapter,
        )

        adapter = FirecrawlAdapter(api_key="fc-test-key")

        with patch.object(adapter, "_client", new_callable=MagicMock) as mock_client:
            mock_client.search = AsyncMock(return_value={"web": []})
            result = await adapter.search("nonexistent query")

        assert result.links == []
        assert result.provider == "firecrawl"

    @pytest.mark.asyncio
    async def test_search_handles_api_error(self):
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.web_search.firecrawl_adapter import (
            FirecrawlAdapter,
        )

        adapter = FirecrawlAdapter(api_key="fc-bad-key")

        with patch.object(adapter, "_client", new_callable=MagicMock) as mock_client:
            mock_client.search = AsyncMock(side_effect=Exception("API Error"))
            result = await adapter.search("test query")

        assert result.links == []
        assert len(result.warnings) == 1
        assert "firecrawl" in result.warnings[0].lower()

    @pytest.mark.asyncio
    async def test_scrape_links_json_mode_extracts_metadata(self):
        """JSON mode returns structured title, DOI, and PDF URL."""
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.web_search.firecrawl_adapter import (
            FirecrawlAdapter,
        )

        adapter = FirecrawlAdapter(api_key="fc-test-key")

        mock_scrape_result = {
            "json": {
                "title": "BRCA1 Mutation in Breast Cancer",
                "doi": "10.1234/example",
                "pdf_url": "https://journal.com/paper.pdf",
                "other_links": ["https://journal.com/supplementary.pdf"],
            },
            "metadata": {"source_url": "https://journal.com/article/1"},
        }

        with patch.object(adapter, "_client", new_callable=MagicMock) as mock_client:
            mock_client.scrape = AsyncMock(return_value=mock_scrape_result)
            links = await adapter.scrape_links("https://journal.com/article/1")

        assert len(links) == 2
        assert links[0].url == "https://journal.com/paper.pdf"
        assert links[0].doi == "10.1234/example"
        assert links[0].title == "BRCA1 Mutation in Breast Cancer"
        assert links[0].source == "firecrawl-json"
        assert links[1].url == "https://journal.com/supplementary.pdf"

    @pytest.mark.asyncio
    async def test_scrape_links_json_doi_only(self):
        """JSON mode with DOI but no PDF URL falls back to DOI landing page."""
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.web_search.firecrawl_adapter import (
            FirecrawlAdapter,
        )

        adapter = FirecrawlAdapter(api_key="fc-test-key")

        mock_scrape_result = {
            "json": {
                "title": "Some Paper",
                "doi": "10.5678/no-pdf",
                "pdf_url": None,
                "other_links": [],
            },
        }

        with patch.object(adapter, "_client", new_callable=MagicMock) as mock_client:
            mock_client.scrape = AsyncMock(return_value=mock_scrape_result)
            links = await adapter.scrape_links("https://journal.com/article/2")

        assert len(links) == 1
        assert links[0].url == "https://doi.org/10.5678/no-pdf"
        assert links[0].doi == "10.5678/no-pdf"
        assert links[0].source == "firecrawl-json-doi"

    @pytest.mark.asyncio
    async def test_scrape_links_falls_back_to_markdown(self):
        """Falls back to markdown+regex when JSON mode returns empty."""
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.web_search.firecrawl_adapter import (
            FirecrawlAdapter,
        )

        adapter = FirecrawlAdapter(api_key="fc-test-key")

        json_result = {"json": {}, "metadata": {}}
        markdown_result = {
            "markdown": '[Download PDF](https://journal.com/paper.pdf)\n<a href="https://journal.com/full.pdf">Full text</a>',
            "metadata": {"source_url": "https://journal.com/article/1"},
        }

        with patch.object(adapter, "_client", new_callable=MagicMock) as mock_client:
            mock_client.scrape = AsyncMock(side_effect=[json_result, markdown_result])
            links = await adapter.scrape_links("https://journal.com/article/1")

        assert len(links) >= 1
        assert any(".pdf" in link.url for link in links)

    @pytest.mark.asyncio
    async def test_scrape_links_falls_back_on_json_error(self):
        """Falls back to markdown when JSON mode raises an exception."""
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.web_search.firecrawl_adapter import (
            FirecrawlAdapter,
        )

        adapter = FirecrawlAdapter(api_key="fc-test-key")

        markdown_result = {
            "markdown": "[PDF](https://journal.com/paper.pdf)",
            "metadata": {},
        }

        with patch.object(adapter, "_client", new_callable=MagicMock) as mock_client:
            mock_client.scrape = AsyncMock(side_effect=[Exception("JSON mode not available"), markdown_result])
            links = await adapter.scrape_links("https://journal.com/article/1")

        assert len(links) >= 1
        assert any(".pdf" in link.url for link in links)
