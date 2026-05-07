"""Tests for web providers — unit tests with mocked dependencies."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.core.ingest_and_digitize_data.literature_acquisition.web_providers import (
    call_web_provider,
    call_pubscholar,
    call_cyberleninka,
    call_hans_publishers,
)
from src.core.ingest_and_digitize_data.literature_acquisition.web.base import (
    safe_json_loads,
    sanitize_filename,
    extract_pdf_links_from_html,
    choose_item,
)


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


class TestWebProviderDispatch:
    @pytest.mark.asyncio
    async def test_unknown_provider(self):
        result = await call_web_provider("unknown_provider", action="search", query="test")
        assert not result.success
        assert "unknown web provider" in result.warnings[0]

    @pytest.mark.asyncio
    async def test_pubscholar_import_error(self):
        with patch.dict("sys.modules", {"src.core.ingest_and_digitize_data.literature_acquisition.web.pubscholar": None}):
            result = await call_pubscholar(action="search", query="test")
            assert not result.success
            assert "not available" in result.warnings[0]

    @pytest.mark.asyncio
    async def test_cyberleninka_import_error(self):
        with patch.dict("sys.modules", {"src.core.ingest_and_digitize_data.literature_acquisition.web.cyberleninka": None}):
            result = await call_cyberleninka(action="search", query="test")
            assert not result.success
            assert "not available" in result.warnings[0]

    @pytest.mark.asyncio
    async def test_hans_import_error(self):
        with patch.dict("sys.modules", {"src.core.ingest_and_digitize_data.literature_acquisition.web.hans_publishers": None}):
            result = await call_hans_publishers(action="search", query="test")
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

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.post = AsyncMock(return_value=mock_response)

            from src.core.ingest_and_digitize_data.literature_acquisition.web.cyberleninka import cyberleninka_search
            result = await cyberleninka_search("test query", limit=10)

            assert result["success"]
            assert len(result["items"]) == 1
            assert result["items"][0]["title"] == "Test Paper"
