"""Integration tests for PubScholar scraper with unified payload interface."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.literature.automated_web.pubscholar.enums import Language, PaperType
from src.domain.literature.automated_web.pubscholar.models import (
    BASE_URL,
    DownloadResponse,
    PaperItem,
    PubScholarPayload,
    SearchParams,
    SearchResponse,
)
from src.domain.literature.automated_web.pubscholar.pubscholar import (
    pubscholar_workflow,
)
from src.domain.literature.automated_web.pubscholar.service import (
    PubScholarService,
    _build_llm_strategy,
    _build_search_js,
    _extract_pdf_links_by_html,
    _safe_json_loads,
    _sanitize_filename,
    _wait_for_results_js,
)


class TestLanguageEnum:
    """Test Language enum."""

    def test_language_values(self):
        assert Language.CHINESE.value == "中文"
        assert Language.ENGLISH.value == "英文"

    def test_language_inheritance(self):
        assert isinstance(Language.CHINESE, str)
        assert isinstance(Language.CHINESE, Language)


class TestPaperTypeEnum:
    """Test PaperType enum."""

    def test_paper_type_values(self):
        assert PaperType.JOURNAL.value == "期刊"
        assert PaperType.PREPRINT.value == "预印本"
        assert PaperType.CONFERENCE.value == "会议"

    def test_paper_type_inheritance(self):
        assert isinstance(PaperType.JOURNAL, str)
        assert isinstance(PaperType.JOURNAL, PaperType)


class TestSearchParams:
    """Test SearchParams model."""

    def test_default_values(self):
        params = SearchParams(keyword="test")
        assert params.keyword == "test"
        assert params.filters == {}
        assert params.limit == 20

    def test_keyword_as_list(self):
        params = SearchParams(keyword=["心脑血管", "遗传"])
        assert params.keyword == ["心脑血管", "遗传"]

    def test_keyword_as_string(self):
        params = SearchParams(keyword="心脑血管")
        assert params.keyword == "心脑血管"

    def test_filters_with_subject(self):
        params = SearchParams(
            keyword="test", filters={"subject": ["临床医学", "生物学"]}
        )
        assert params.filters["subject"] == ["临床医学", "生物学"]

    def test_limit_validation(self):
        params = SearchParams(keyword="test", limit=100)
        assert params.limit == 50

        params = SearchParams(keyword="test", limit=0)
        assert params.limit == 1


class TestPubScholarPayload:
    """Test PubScholarPayload - unified payload model."""

    def test_default_values(self):
        payload = PubScholarPayload(search_params=SearchParams(keyword="test"))
        assert payload.action == "search"
        assert payload.base_url == BASE_URL
        assert payload.download_path == "./downloads"
        assert payload.llm_provider == "deepseek"
        assert payload.selected_index == 0

    def test_search_action(self):
        payload = PubScholarPayload(
            action="search",
            search_params=SearchParams(
                keyword=["心脑血管", "遗传"],
                filters={"subject": ["临床医学", "生物学"]},
                limit=20,
            ),
            download_path="./downloads",
        )
        assert payload.action == "search"
        assert payload.search_params.keyword == ["心脑血管", "遗传"]

    def test_download_action(self):
        payload = PubScholarPayload(
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
        payload = PubScholarPayload(search_params=SearchParams(keyword="test"))
        assert payload.keyword == "test"

    def test_keyword_property_with_list(self):
        payload = PubScholarPayload(
            search_params=SearchParams(keyword=["心脑血管", "遗传"])
        )
        assert payload.keyword == "心脑血管 遗传"

    def test_max_results_from_limit(self):
        payload = PubScholarPayload(
            search_params=SearchParams(keyword="test", limit=30)
        )
        assert payload.max_results == 30

    def test_to_search_filters(self):
        payload = PubScholarPayload(
            search_params=SearchParams(
                keyword="test",
                filters={
                    "language": "英文",
                    "paper_types": ["期刊"],
                    "full_text_only": False,
                    "subject": ["临床医学"],
                },
            )
        )
        filters = payload.to_search_filters()
        assert filters.language == Language.ENGLISH
        assert PaperType.JOURNAL in filters.paper_types
        assert filters.full_text_only is False
        assert "临床医学" in filters.subjects

    def test_model_validate_from_dict(self):
        payload = {
            "action": "search",
            "search_params": {
                "keyword": ["心脑血管", "遗传"],
                "filters": {"subject": ["临床医学", "生物学"]},
                "limit": 20,
            },
            "download_path": "./downloads",
            "llm_provider": "ollama",
        }
        req = PubScholarPayload.model_validate(payload)
        assert req.action == "search"
        assert req.search_params.keyword == ["心脑血管", "遗传"]
        assert req.search_params.limit == 20

    def test_model_validate_download(self):
        payload = {
            "action": "download",
            "search_params": {
                "keyword": ["心脑血管", "遗传"],
                "filters": {"subject": ["临床医学", "生物学"]},
                "limit": 20,
            },
            "selected_index": 0,
            "download_path": "./downloads",
            "llm_provider": "ollama",
        }
        req = PubScholarPayload.model_validate(payload)
        assert req.action == "download"
        assert req.selected_index == 0


class TestPaperItem:
    """Test PaperItem model."""

    def test_minimal_item(self):
        item = PaperItem(title="Test Paper")
        assert item.title == "Test Paper"
        assert item.authors is None

    def test_with_subjects(self):
        item = PaperItem(title="Test Paper", subjects=["临床医学", "生物学"])
        assert item.subjects == ["临床医学", "生物学"]


class TestSearchResponse:
    """Test SearchResponse model."""

    def test_with_total_count(self):
        items = [PaperItem(title="Test Paper")]
        resp = SearchResponse(success=True, items=items, total_count=100)
        assert resp.success is True
        assert resp.total_count == 100


class TestDownloadResponse:
    """Test DownloadResponse model."""

    def test_success_response(self):
        resp = DownloadResponse(
            success=True,
            pdf_url="https://example.com/paper.pdf",
            file_path="./downloads/paper.pdf",
        )
        assert resp.success is True
        assert resp.pdf_url is not None
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
        result = _safe_json_loads("")
        assert result == {}

    def test_json_in_mixed_content(self):
        text = 'Some text before {"key": "value"} some text after'
        result = _safe_json_loads(text)
        assert result == {"key": "value"}

    def test_invalid_json(self):
        text = "not json at all"
        result = _safe_json_loads(text)
        assert result == {}

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


class TestBuildLlmStrategy:
    """Test _build_llm_strategy helper function."""

    def test_ollama_no_token_required(self):
        schema = {"type": "object", "properties": {}}
        strategy = _build_llm_strategy(
            provider="ollama",
            token=None,
            schema=schema,
            instruction="test instruction",
        )
        assert strategy is not None

    def test_other_provider_requires_token(self):
        schema = {"type": "object", "properties": {}}
        with pytest.raises(ValueError, match="requires api_token"):
            _build_llm_strategy(
                provider="openai",
                token=None,
                schema=schema,
                instruction="test instruction",
            )


class TestBuildSearchJs:
    """Test _build_search_js helper function."""

    def test_basic_search(self):
        js = _build_search_js(
            keyword="test",
            language=None,
            paper_types=[],
            full_text_only=False,
        )
        assert "async () =>" in js
        assert "test" in js

    def test_with_language(self):
        js = _build_search_js(
            keyword="test",
            language="中文",
            paper_types=[],
            full_text_only=False,
        )
        assert "\\u4e2d\\u6587" in js or "中文" in js

    def test_with_paper_types(self):
        js = _build_search_js(
            keyword="test",
            language=None,
            paper_types=["期刊", "会议"],
            full_text_only=False,
        )
        assert "\\u671f\\u520a" in js or "期刊" in js


class TestWaitForResultsJs:
    """Test _wait_for_results_js helper function."""

    def test_returns_js_function(self):
        js = _wait_for_results_js()
        assert "() =>" in js
        assert "document.evaluate" in js


class TestExtractPdfLinksByHtml:
    """Test _extract_pdf_links_by_html helper function."""

    def test_extract_pdf_links(self):
        html = """
        <html>
            <a href="https://example.com/paper.pdf">PDF</a>
            <a href="https://example.com/page.html">HTML</a>
            <a href="/relative/path.pdf">Relative PDF</a>
        </html>
        """
        links = _extract_pdf_links_by_html(html, "https://example.com")
        assert len(links) == 2
        assert "https://example.com/paper.pdf" in links

    def test_no_pdf_links(self):
        html = """
        <html>
            <a href="https://example.com/page.html">HTML</a>
        </html>
        """
        links = _extract_pdf_links_by_html(html, "https://example.com")
        assert links == []

    def test_deduplication(self):
        html = """
        <html>
            <a href="https://example.com/paper.pdf">PDF 1</a>
            <a href="https://example.com/paper.pdf">PDF 2</a>
        </html>
        """
        links = _extract_pdf_links_by_html(html, "https://example.com")
        assert len(links) == 1


class TestPubScholarService:
    """Test PubScholarService class with unified payload."""

    def test_init_default_base_url(self):
        service = PubScholarService()
        assert service.base_url == "https://pubscholar.cn"

    def test_init_custom_base_url(self):
        service = PubScholarService(base_url="https://custom.url/")
        assert service.base_url == "https://custom.url"

    @pytest.mark.asyncio
    async def test_search_with_unified_payload(self):
        """Test search with unified payload interface."""
        service = PubScholarService()

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.extracted_content = '{"items": [{"title": "Test Paper"}]}'
        mock_result.markdown = MagicMock()
        mock_result.markdown.fit_markdown = "test markdown"

        payload = PubScholarPayload(
            action="search",
            search_params=SearchParams(
                keyword=["心脑血管", "遗传"],
                filters={"subject": ["临床医学", "生物学"]},
                limit=10,
            ),
            llm_provider="ollama",
            llm_api_token="test-token",
        )

        with patch.object(
            service, "_search_via_duckduckgo", AsyncMock(return_value=[])
        ):
            with patch.object(service, "browser_config"):
                with patch(
                    "src.domain.literature.automated_web.pubscholar.service.AsyncWebCrawler"
                ) as mock_crawler_cls:
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
        service = PubScholarService()

        mock_result = MagicMock()
        mock_result.success = False
        mock_result.error_message = "crawl_failed"

        payload = PubScholarPayload(
            action="search",
            search_params=SearchParams(keyword="test"),
            llm_provider="ollama",
            llm_api_token="test-token",
        )

        with patch.object(
            service, "_search_via_duckduckgo", AsyncMock(return_value=[])
        ):
            with patch.object(service, "browser_config"):
                with patch(
                    "src.domain.literature.automated_web.pubscholar.service.AsyncWebCrawler"
                ) as mock_crawler_cls:
                    mock_crawler = AsyncMock()
                    mock_crawler.arun = AsyncMock(return_value=mock_result)
                    mock_crawler_cls.return_value.__aenter__.return_value = mock_crawler

                    result = await service.search(payload)

                    assert result.success is False
                    assert any("crawl_failed" in w for w in result.warnings)


class TestPubscholarWorkflow:
    """Test pubscholar_workflow with unified payload interface."""

    @pytest.mark.asyncio
    async def test_search_action(self):
        """Test workflow with search action."""
        payload = {
            "action": "search",
            "search_params": {
                "keyword": ["心脑血管", "遗传"],
                "filters": {"subject": ["临床医学", "生物学"]},
                "limit": 20,
            },
            "download_path": "./downloads",
            "llm_provider": "ollama",
        }

        with patch(
            "src.domain.literature.automated_web.pubscholar.pubscholar.PubScholarService"
        ) as MockService:
            mock_service = MockService.return_value
            mock_service.search = AsyncMock(
                return_value=SearchResponse(
                    success=True,
                    items=[PaperItem(title="Test Paper")],
                    total_count=1,
                )
            )

            result = await pubscholar_workflow(payload)

            assert result["success"] is True
            assert len(result["items"]) == 1
            assert result["total_count"] == 1

    @pytest.mark.asyncio
    async def test_download_action(self):
        """Test workflow with download action."""
        payload = {
            "action": "download",
            "search_params": {
                "keyword": ["心脑血管", "遗传"],
                "filters": {"subject": ["临床医学", "生物学"]},
                "limit": 20,
            },
            "selected_index": 0,
            "download_path": "./downloads",
            "llm_provider": "ollama",
        }

        with patch(
            "src.domain.literature.automated_web.pubscholar.pubscholar.PubScholarService"
        ) as MockService:
            mock_service = MockService.return_value
            mock_service.download = AsyncMock(
                return_value=DownloadResponse(
                    success=True,
                    pdf_url="https://example.com/paper.pdf",
                    file_path="./downloads/paper.pdf",
                )
            )

            result = await pubscholar_workflow(payload)

            assert result["success"] is True
            assert "paper.pdf" in result["pdf_url"]

    @pytest.mark.asyncio
    async def test_invalid_request(self):
        """Test workflow with invalid request."""
        payload = {"invalid": "data"}

        result = await pubscholar_workflow(payload)

        assert result["success"] is False
        assert any("invalid_request" in w for w in result["warnings"])

    @pytest.mark.asyncio
    async def test_default_action_is_search(self):
        """Test that default action is search when not specified."""
        payload = {
            "search_params": {"keyword": "test", "limit": 10},
        }

        with patch(
            "src.domain.literature.automated_web.pubscholar.pubscholar.PubScholarService"
        ) as MockService:
            mock_service = MockService.return_value
            mock_service.search = AsyncMock(
                return_value=SearchResponse(success=True, items=[])
            )

            result = await pubscholar_workflow(payload)

            assert result["success"] is True
            mock_service.search.assert_called_once()
