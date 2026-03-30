"""Unit tests for Hans Publishers module focusing on models only."""

import importlib.util
import sys
from pathlib import Path

import pytest

# Dynamically load the models module to avoid import chain issues
models_path = Path("src/domain/literature/automated_web/hans_publishers/models.py")
spec = importlib.util.spec_from_file_location("hanspub_models", models_path)
hanspub_models = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hanspub_models)

# Import the specific classes we need
SearchParams = hanspub_models.SearchParams
HansPubPayload = hanspub_models.HansPubPayload
SearchResponse = hanspub_models.SearchResponse
DownloadResponse = hanspub_models.DownloadResponse
PaperItem = hanspub_models.PaperItem
PaperList = hanspub_models.PaperList


class TestHansPubModels:
    """Test Hans Publishers Pydantic models."""

    def test_search_params_validation(self):
        """Test SearchParams validation."""
        # Valid params
        params = SearchParams(keyword="test", limit=10)
        assert params.keyword == "test"
        assert params.limit == 10

        # Limit range validation
        params_clamped = SearchParams(keyword="test", limit=100)
        assert params_clamped.limit == 50  # Max limit is 50

        params_clamped_min = SearchParams(keyword="test", limit=0)
        assert params_clamped_min.limit == 1  # Min limit is 1

    def test_search_params_with_list_keyword(self):
        """Test SearchParams with list of keywords."""
        params = SearchParams(keyword=["test1", "test2"], limit=5)
        assert params.keyword == ["test1", "test2"]
        assert params.limit == 5

    def test_paper_item_creation(self):
        """Test PaperItem creation."""
        item = PaperItem(
            title="Test Paper",
            authors="Test Author",
            year="2023",
            journal="Test Journal",
            subject="Computer Science",
            detail_link="https://example.com/paper",
        )
        assert item.title == "Test Paper"
        assert item.authors == "Test Author"
        assert item.year == "2023"
        assert item.journal == "Test Journal"
        assert item.subject == "Computer Science"
        assert item.detail_link == "https://example.com/paper"

    def test_paper_list_creation(self):
        """Test PaperList creation."""
        item1 = PaperItem(title="Paper 1", authors="Author 1")
        item2 = PaperItem(title="Paper 2", authors="Author 2")
        paper_list = PaperList(items=[item1, item2])
        assert len(paper_list.items) == 2
        assert paper_list.items[0].title == "Paper 1"
        assert paper_list.items[1].title == "Paper 2"

    def test_search_response_creation(self):
        """Test SearchResponse creation."""
        response = SearchResponse(
            success=True,
            items=[{"title": "Test", "index": 0}],
            warnings=[],
            raw_excerpt="Sample excerpt",
            total_count=1,
        )
        assert response.success is True
        assert len(response.items) == 1
        assert response.items[0]["title"] == "Test"
        assert response.total_count == 1

    def test_download_response_creation(self):
        """Test DownloadResponse creation."""
        response = DownloadResponse(
            success=True,
            pdf_url="https://example.com/file.pdf",
            file_path="/tmp/file.pdf",
            warnings=[],
        )
        assert response.success is True
        assert response.pdf_url == "https://example.com/file.pdf"
        assert response.file_path == "/tmp/file.pdf"

    def test_hanspub_payload_creation(self):
        """Test HansPubPayload creation."""
        payload = HansPubPayload(search_params=SearchParams(keyword="test", limit=10))
        assert payload.search_params.keyword == "test"
        assert payload.search_params.limit == 10

    def test_hanspub_payload_keyword_property(self):
        """Test HansPubPayload keyword property."""
        payload = HansPubPayload(search_params=SearchParams(keyword="test", limit=10))
        assert payload.keyword == ["test"]

        payload_list = HansPubPayload(
            search_params=SearchParams(keyword=["test1", "test2"], limit=10)
        )
        assert payload_list.keyword == ["test1", "test2"]

    def test_hanspub_payload_subjects_property(self):
        """Test HansPubPayload subjects property."""
        payload = HansPubPayload(
            search_params=SearchParams(
                keyword="test", limit=10, filters={"subject": ["Clinical Medicine"]}
            )
        )
        assert payload.subjects == ["Clinical Medicine"]

        payload_no_subjects = HansPubPayload(
            search_params=SearchParams(keyword="test", limit=10)
        )
        assert payload_no_subjects.subjects == []

    def test_hanspub_payload_max_results_property(self):
        """Test HansPubPayload max_results property."""
        payload = HansPubPayload(search_params=SearchParams(keyword="test", limit=25))
        assert payload.max_results == 25

    def test_hanspub_payload_properties_with_defaults(self):
        """Test HansPubPayload properties with default values."""
        payload = HansPubPayload(search_params=SearchParams(keyword="test"))
        assert payload.action == "search"
        assert payload.base_url == "https://www.hanspub.org/"
        assert payload.download_path == "./downloads"
        assert payload.timeout_ms == 80000
        assert payload.selected_index == 0
