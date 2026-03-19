"""Integration tests for CyberLeninka service."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add the cyberleninka directory to sys.path for direct module imports
cyberleninka_dir = (
    Path(__file__).parent.parent.parent
    / "src"
    / "domain"
    / "literature"
    / "cyberleninka"
)
sys.path.insert(0, str(cyberleninka_dir))

# Now import directly (modules will use absolute imports)
from cyberleninka import cyberleninka_workflow
from enums import Subject
from locators import (
    XPATH_DOWNLOAD_BTN,
    XPATH_RESULTS,
    XPATH_SEARCH_BUTTON,
    XPATH_SEARCH_INPUT,
    XPATH_SUBJECT_FILTER,
)
from models import (
    BASE_URL,
    CyberleninkaPayload,
    DownloadResponse,
    PaperItem,
    PaperList,
    SearchParams,
    SearchResponse,
)
from service import (
    CyberLeninkaService,
    _build_search_js,
    _choose_item,
    _extract_pdf_link,
    _safe_json_loads,
    _sanitize_filename,
    _wait_for_xpath,
)


class TestSubjectEnum:
    """Test Subject enum."""

    def test_subject_values(self):
        assert Subject.MATHEMATICS.value == "Математика"
        assert Subject.COMPUTER_SCIENCE.value == "Информатика"
        assert Subject.MEDICINE.value == "Медицина"

    def test_subject_inheritance(self):
        assert isinstance(Subject.MATHEMATICS, str)
        assert isinstance(Subject.MATHEMATICS, Subject)


class TestSearchParams:
    """Test SearchParams model."""

    def test_default_values(self):
        params = SearchParams(keyword="test")
        assert params.keyword == "test"
        assert params.filters == {}
        assert params.limit == 20

    def test_keyword_as_list(self):
        params = SearchParams(keyword=["машинное обучение", "нейронные сети"])
        assert params.keyword == ["машинное обучение", "нейронные сети"]

    def test_keyword_as_string(self):
        params = SearchParams(keyword="машинное обучение")
        assert params.keyword == "машинное обучение"

    def test_filters_with_subject(self):
        params = SearchParams(keyword="test", filters={"subject": ["Информатика"]})
        assert params.filters["subject"] == ["Информатика"]

    def test_limit_validation(self):
        params = SearchParams(keyword="test", limit=100)
        assert params.limit == 50

        params = SearchParams(keyword="test", limit=0)
        assert params.limit == 1


class TestCyberleninkaPayload:
    """Test CyberleninkaPayload - unified payload model."""

    def test_default_values(self):
        payload = CyberleninkaPayload(search_params=SearchParams(keyword="test"))
        assert payload.action == "search"
        assert payload.base_url == BASE_URL
        assert payload.download_path == "./downloads"
        assert payload.llm_provider == "ollama"
        assert payload.selected_index == 0

    def test_search_action(self):
        payload = CyberleninkaPayload(
            action="search",
            search_params=SearchParams(
                keyword=["машинное обучение", "нейронные сети"],
                filters={"subject": ["Информатика"]},
                limit=20,
            ),
            download_path="./downloads",
        )
        assert payload.action == "search"
        assert payload.keyword == ["машинное обучение", "нейронные сети"]

    def test_download_action(self):
        payload = CyberleninkaPayload(
            action="download",
            search_params=SearchParams(keyword="test", limit=10),
            selected_index=0,
            selected_title="Test Paper",
            download_path="./downloads",
        )
        assert payload.action == "download"
        assert payload.selected_index == 0
        assert payload.selected_title == "Test Paper"

    def test_keyword_property_with_string(self):
        payload = CyberleninkaPayload(search_params=SearchParams(keyword="test"))
        assert payload.keyword == ["test"]

    def test_keyword_property_with_list(self):
        payload = CyberleninkaPayload(
            search_params=SearchParams(keyword=["машинное обучение", "нейронные сети"])
        )
        assert payload.keyword == ["машинное обучение", "нейронные сети"]

    def test_subjects_property(self):
        payload = CyberleninkaPayload(
            search_params=SearchParams(
                keyword="test", filters={"subject": ["Информатика", "Математика"]}
            )
        )
        assert payload.subjects == ["Информатика", "Математика"]

    def test_max_results_from_limit(self):
        payload = CyberleninkaPayload(
            search_params=SearchParams(keyword="test", limit=30)
        )
        assert payload.max_results == 30

    def test_model_validate_from_dict(self):
        payload = {
            "action": "search",
            "search_params": {
                "keyword": ["машинное обучение", "нейронные сети"],
                "filters": {"subject": ["Информатика"]},
                "limit": 20,
            },
            "download_path": "./downloads",
            "llm_provider": "ollama",
        }
        req = CyberleninkaPayload.model_validate(payload)
        assert req.action == "search"
        assert req.keyword == ["машинное обучение", "нейронные сети"]
        assert req.subjects == ["Информатика"]

    def test_model_validate_download(self):
        payload = {
            "action": "download",
            "search_params": {
                "keyword": ["машинное обучение"],
                "filters": {"subject": ["Информатика"]},
                "limit": 20,
            },
            "selected_index": 0,
            "download_path": "./downloads",
            "llm_provider": "ollama",
        }
        req = CyberleninkaPayload.model_validate(payload)
        assert req.action == "download"
        assert req.selected_index == 0


class TestPaperItem:
    """Test PaperItem model."""

    def test_minimal_item(self):
        item = PaperItem(title="Test Paper")
        assert item.title == "Test Paper"
        assert item.authors is None

    def test_with_detail_link(self):
        item = PaperItem(
            title="Test Paper", detail_link="https://cyberleninka.ru/paper"
        )
        assert item.detail_link == "https://cyberleninka.ru/paper"


class TestSearchResponse:
    """Test SearchResponse model."""

    def test_with_total_count(self):
        items = [{"title": "Test Paper", "index": 0}]
        resp = SearchResponse(success=True, items=items, total_count=100)
        assert resp.success is True
        assert resp.total_count == 100


class TestDownloadResponse:
    """Test DownloadResponse model."""

    def test_success_response(self):
        resp = DownloadResponse(
            success=True,
            pdf_url="https://cyberleninka.ru/paper.pdf",
            file_path="./downloads/paper.pdf",
        )
        assert resp.success is True
        assert "paper.pdf" in resp.pdf_url


class TestSafeJsonLoads:
    """Test _safe_json_loads helper function."""

    def test_valid_json(self):
        text = '{"key": "value"}'
        result = _safe_json_loads(text)
        assert result == {"key": "value"}

    def test_empty_string(self):
        result = _safe_json_loads("")
        assert result == {}

    def test_none_input(self):
        result = _safe_json_loads(None)
        assert result == {}

    def test_json_in_mixed_content(self):
        text = 'Some text before {"key": "value"} some text after'
        result = _safe_json_loads(text)
        assert result == {"key": "value"}

    def test_json_array(self):
        text = '[{"item": 1}, {"item": 2}]'
        result = _safe_json_loads(text)
        assert len(result) == 2


class TestSanitizeFilename:
    """Test _sanitize_filename helper function."""

    def test_normal_filename(self):
        result = _sanitize_filename("test_paper.pdf")
        assert result == "test_paper.pdf"

    def test_filename_with_invalid_chars(self):
        result = _sanitize_filename("test/paper:name.pdf")
        assert "/" not in result
        assert ":" not in result

    def test_filename_with_spaces(self):
        result = _sanitize_filename("test   paper   with   spaces.pdf")
        assert "   " not in result
        assert "test paper with spaces.pdf" == result

    def test_empty_filename(self):
        result = _sanitize_filename("")
        assert result == "paper"

    def test_long_filename(self):
        long_name = "a" * 200
        result = _sanitize_filename(long_name)
        assert len(result) <= 120


class TestBuildSearchJs:
    """Test _build_search_js helper function."""

    def test_basic_search(self):
        js = _build_search_js(keywords=["test"], subjects=[])
        assert "async () =>" in js
        assert "test" in js

    def test_with_subjects(self):
        js = _build_search_js(keywords=["test"], subjects=["Информатика"])
        assert (
            "Информатика" in js
            or "\\u0418\\u043d\\u0444\\u043e\\u0440\\u043c\\u0430\\u0442\\u0438\\u043a\\u0430"
            in js
        )

    def test_with_multiple_keywords(self):
        js = _build_search_js(
            keywords=["машинное обучение", "нейронные сети"], subjects=[]
        )
        assert "async () =>" in js


class TestWaitForXpath:
    """Test _wait_for_xpath helper function."""

    def test_returns_js_function(self):
        js = _wait_for_xpath(XPATH_RESULTS)
        assert "() =>" in js
        assert "document.evaluate" in js


class TestExtractPdfLink:
    """Test _extract_pdf_link helper function."""

    def test_extract_pdf_link_with_lxml(self):
        html = """
        <html>
            <button id="btn-download" data-href="/paper.pdf">Download</button>
        </html>
        """
        link = _extract_pdf_link(html, "https://cyberleninka.ru/")
        assert link == "https://cyberleninka.ru/paper.pdf"

    def test_no_pdf_link(self):
        html = """
        <html>
            <button id="btn-download">Download</button>
        </html>
        """
        link = _extract_pdf_link(html, "https://cyberleninka.ru/")
        assert link is None


class TestChooseItem:
    """Test _choose_item helper function."""

    def test_choose_by_index(self):
        items = [
            {"title": "Paper 1", "index": 0},
            {"title": "Paper 2", "index": 1},
        ]
        chosen = _choose_item(items, selected_index=1, selected_title=None)
        assert chosen["title"] == "Paper 2"

    def test_choose_by_title(self):
        items = [
            {"title": "Paper 1", "index": 0},
            {"title": "Paper 2", "index": 1},
        ]
        chosen = _choose_item(items, selected_index=0, selected_title="Paper 2")
        assert chosen["title"] == "Paper 2"

    def test_invalid_index(self):
        items = [{"title": "Paper 1", "index": 0}]
        chosen = _choose_item(items, selected_index=5, selected_title=None)
        assert chosen is None

    def test_title_not_found_fallback(self):
        items = [{"title": "Paper 1", "index": 0}]
        # When title not found, it falls back to index if valid
        chosen = _choose_item(items, selected_index=0, selected_title="Nonexistent")
        assert chosen is not None
        assert chosen["title"] == "Paper 1"


class TestCyberLeninkaService:
    """Test CyberLeninkaService class."""

    def test_init_default_base_url(self):
        service = CyberLeninkaService()
        assert service.base_url == "https://cyberleninka.ru"

    def test_init_custom_base_url(self):
        service = CyberLeninkaService(base_url="https://custom.url/")
        assert service.base_url == "https://custom.url"

    @pytest.mark.asyncio
    async def test_search_with_unified_payload(self):
        """Test search with unified payload interface."""
        service = CyberLeninkaService()

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.extracted_content = '{"items": [{"title": "Test Paper"}]}'
        mock_result.markdown = "test markdown"

        payload = CyberleninkaPayload(
            action="search",
            search_params=SearchParams(
                keyword=["машинное обучение", "нейронные сети"],
                filters={"subject": ["Информатика"]},
                limit=10,
            ),
        )

        with patch.object(service, "browser_config"):
            with patch("service.AsyncWebCrawler") as mock_crawler_cls:
                mock_crawler = AsyncMock()
                mock_crawler.arun = AsyncMock(return_value=mock_result)
                mock_crawler_cls.return_value.__aenter__.return_value = mock_crawler

                result = await service.search(payload)

                assert result.success is True
                assert len(result.items) == 1
                assert result.total_count == 1

    @pytest.mark.asyncio
    async def test_search_failure(self):
        """Test failed search."""
        service = CyberLeninkaService()

        mock_result = MagicMock()
        mock_result.success = False
        mock_result.error_message = "crawl_failed"

        payload = CyberleninkaPayload(
            action="search",
            search_params=SearchParams(keyword="test"),
        )

        with patch.object(service, "browser_config"):
            with patch("service.AsyncWebCrawler") as mock_crawler_cls:
                mock_crawler = AsyncMock()
                mock_crawler.arun = AsyncMock(return_value=mock_result)
                mock_crawler_cls.return_value.__aenter__.return_value = mock_crawler

                result = await service.search(payload)

                assert result.success is False
                assert "crawl_failed" in result.warnings


class TestCyberleninkaWorkflow:
    """Test cyberleninka_workflow with unified payload interface."""

    @pytest.mark.asyncio
    async def test_search_action(self):
        """Test workflow with search action."""
        payload = {
            "action": "search",
            "search_params": {
                "keyword": ["машинное обучение", "нейронные сети"],
                "filters": {"subject": ["Информатика"]},
                "limit": 20,
            },
            "download_path": "./downloads",
            "llm_provider": "ollama",
        }

        with patch("cyberleninka.CyberLeninkaService") as MockService:
            mock_service = MockService.return_value
            mock_service.search = AsyncMock(
                return_value=SearchResponse(
                    success=True,
                    items=[{"title": "Test Paper", "index": 0}],
                    total_count=1,
                )
            )

            result = await cyberleninka_workflow(payload)

            assert result["success"] is True
            assert len(result["items"]) == 1
            assert result["total_count"] == 1

    @pytest.mark.asyncio
    async def test_download_action(self):
        """Test workflow with download action."""
        payload = {
            "action": "download",
            "search_params": {
                "keyword": ["машинное обучение"],
                "filters": {"subject": ["Информатика"]},
                "limit": 20,
            },
            "selected_index": 0,
            "download_path": "./downloads",
            "llm_provider": "ollama",
        }

        with patch("cyberleninka.CyberLeninkaService") as MockService:
            mock_service = MockService.return_value
            mock_service.download = AsyncMock(
                return_value=DownloadResponse(
                    success=True,
                    pdf_url="https://cyberleninka.ru/paper.pdf",
                    file_path="./downloads/paper.pdf",
                )
            )

            result = await cyberleninka_workflow(payload)

            assert result["success"] is True
            assert "paper.pdf" in result["pdf_url"]

    @pytest.mark.asyncio
    async def test_invalid_request(self):
        """Test workflow with missing required fields for download."""
        payload = {
            "action": "download",
        }

        with patch("cyberleninka.CyberLeninkaService") as MockService:
            mock_service = MockService.return_value
            mock_service.download = AsyncMock(
                return_value=DownloadResponse(
                    success=False, warnings=["no_search_results"]
                )
            )

            result = await cyberleninka_workflow(payload)

            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_default_action_is_search(self):
        """Test that default action is search when not specified."""
        payload = {
            "search_params": {"keyword": "test", "limit": 10},
        }

        with patch("cyberleninka.CyberLeninkaService") as MockService:
            mock_service = MockService.return_value
            mock_service.search = AsyncMock(
                return_value=SearchResponse(success=True, items=[])
            )

            result = await cyberleninka_workflow(payload)

            assert result["success"] is True
            mock_service.search.assert_called_once()
