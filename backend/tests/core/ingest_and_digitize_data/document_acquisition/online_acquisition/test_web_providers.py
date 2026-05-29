"""Tests for web providers — unit tests with mocked dependencies."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.web_providers import (
    call_web_provider,
)
from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.web.base import (
    safe_json_loads,
    extract_pdf_links_from_html,
    scrape_html_elements,
    choose_item,
    build_js_helpers,
    resolve_llm_config,
)
from src.utils.text import sanitize_filename


class TestBaseUtilities:
    def test_safe_json_loads_valid(self):
        assert safe_json_loads('{"key": "value"}') == {"key": "value"}

    def test_safe_json_loads_mixed(self):
        result = safe_json_loads('some text {"key": "value"} more text')
        assert result == {"key": "value"}

    def test_safe_json_loads_empty(self):
        assert safe_json_loads("") == {}

    def test_sanitize_filename(self):
        assert sanitize_filename('test: file? name') == 'test_ file_ name'

    def test_sanitize_filename_empty(self):
        assert sanitize_filename("") == "paper"

    def test_extract_pdf_links(self):
        html = '<a href="paper.pdf">Download</a><a href="other.html">Link</a>'
        links = extract_pdf_links_from_html(html, "https://example.com")
        assert len(links) == 1
        assert "paper.pdf" in links[0]

    def test_extract_pdf_links_meta(self):
        html = '<meta name="citation_pdf_url" content="https://example.com/paper.pdf">'
        links = extract_pdf_links_from_html(html, "https://example.com")
        assert len(links) == 1
        assert links[0] == "https://example.com/paper.pdf"

    def test_choose_item_by_index(self):
        items = [{"title": "A"}, {"title": "B"}]
        assert choose_item(items, 1, None)["title"] == "B"

    def test_choose_item_by_title(self):
        items = [{"title": "Alpha Paper"}, {"title": "Beta Paper"}]
        assert choose_item(items, 0, "Beta")["title"] == "Beta Paper"

    def test_choose_item_out_of_range(self):
        items = [{"title": "A"}]
        assert choose_item(items, 5, None) is None

    def test_build_js_helpers_contains_functions(self):
        js = build_js_helpers()
        assert "const sleep" in js
        assert "const click" in js
        assert "const input" in js
        assert "const clickByText" in js


class TestWebProviderDispatch:
    @pytest.mark.asyncio
    async def test_unknown_provider(self):
        result = await call_web_provider("unknown_provider", action="search", query="test")
        assert not result.success
        assert "unknown web provider" in result.warnings[0]

    @pytest.mark.asyncio
    async def test_pubscholar_import_error(self):
        with patch.dict("sys.modules", {"src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.web.pubscholar": None}):
            result = await call_web_provider("pubscholar", action="search", query="test")
            assert not result.success
            assert "not available" in result.warnings[0]

    @pytest.mark.asyncio
    async def test_cyberleninka_import_error(self):
        with patch.dict("sys.modules", {"src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.web.cyberleninka": None}):
            result = await call_web_provider("cyberleninka", action="search", query="test")
            assert not result.success
            assert "not available" in result.warnings[0]

    @pytest.mark.asyncio
    async def test_hans_import_error(self):
        with patch.dict("sys.modules", {"src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.web.hans_publishers": None}):
            result = await call_web_provider("hans_publishers", action="search", query="test")
            assert not result.success
            assert "not available" in result.warnings[0]


class TestCyberleninkaSearch:
    @pytest.mark.asyncio
    async def test_api_search_success(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "articles": [
                {
                    "name": "Test Paper",
                    "authors": ["Author A"],
                    "year": 2024,
                    "journal": "Test Journal",
                    "link": "/article/test-paper",
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_async_client = AsyncMock()
        mock_async_client.post = AsyncMock(return_value=mock_response)
        mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
        mock_async_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.web.cyberleninka.httpx.AsyncClient", return_value=mock_async_client):
            from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.web.cyberleninka import cyberleninka_search
            result = await cyberleninka_search("test query", limit=10)

            assert result["success"]
            assert len(result["items"]) == 1
            assert result["items"][0]["title"] == "Test Paper"

    @pytest.mark.asyncio
    async def test_api_search_empty_query(self):
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.web.cyberleninka import cyberleninka_search
        result = await cyberleninka_search("", limit=10)
        assert not result["success"]


class TestCyberleninkaDownload:
    @pytest.mark.asyncio
    async def test_download_no_search_results(self):
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.web.cyberleninka import cyberleninka_download
        with patch(
            "src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.web.cyberleninka.cyberleninka_search",
            new_callable=AsyncMock,
            return_value={"success": False, "items": [], "warnings": []},
        ):
            result = await cyberleninka_download("nonexistent paper")
            assert not result["success"]
            assert "no_search_results" in result["warnings"]


class TestResolveLlmConfig:
    def test_env_fallback(self, monkeypatch):
        monkeypatch.delenv("CRAWL4AI_LLM_PROVIDER", raising=False)
        monkeypatch.delenv("CRAWL4AI_LLM_API_KEY", raising=False)
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        monkeypatch.setenv("CRAWL4AI_LLM_PROVIDER", "openai")
        monkeypatch.setenv("CRAWL4AI_LLM_API_KEY", "test-key")
        provider, key = resolve_llm_config()
        assert provider == "openai"
        assert key == "test-key"


class TestRustIntegration:
    def test_extract_pdf_links_rust_or_fallback(self):
        """Verify extract_pdf_links_from_html works (Rust or BS4 fallback)."""
        html = '<a href="paper.pdf">Download</a><a href="other.html">Link</a>'
        links = extract_pdf_links_from_html(html, "https://example.com")
        assert len(links) == 1
        assert "paper.pdf" in links[0]

    def test_extract_pdf_links_meta_rust_or_fallback(self):
        html = '<meta name="citation_pdf_url" content="https://example.com/paper.pdf">'
        links = extract_pdf_links_from_html(html, "https://example.com")
        assert len(links) == 1
        assert links[0] == "https://example.com/paper.pdf"

    def test_scrape_html_elements(self):
        html = '<html><body><div class="item">Hello</div><div class="item">World</div></body></html>'
        result = scrape_html_elements(html, "div.item")
        assert len(result) == 2
        assert result[0]["text"] == "Hello"
