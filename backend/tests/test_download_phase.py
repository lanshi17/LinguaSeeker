"""Tests for the download phase of the refactored workflow."""

import pytest
from unittest.mock import AsyncMock, patch


class TestResolveOaUrl:
    def test_resolve_from_unpaywall_downloads(self):
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.gateway import resolve_oa_url
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.contracts import (
            OnlineAcquisitionGatewayResult,
        )

        result = OnlineAcquisitionGatewayResult(
            provider="unpaywall",
            success=True,
            items=[{"best_oa_location": {"url_for_pdf": "https://example.com/paper.pdf"}}],
            downloads=[{"pdf_url": "https://example.com/paper.pdf"}],
            warnings=[],
            raw=None,
            meta=None,
            source_trace=[],
        )
        url = resolve_oa_url(result)
        assert url == "https://example.com/paper.pdf"

    def test_resolve_from_pmcid(self):
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.gateway import resolve_oa_url
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.contracts import (
            OnlineAcquisitionGatewayResult,
        )

        result = OnlineAcquisitionGatewayResult(
            provider="pmc",
            success=True,
            items=[{"pmcid": "PMC1234567", "title": "Test"}],
            downloads=[],
            warnings=[],
            raw=None,
            meta=None,
            source_trace=[],
        )
        url = resolve_oa_url(result)
        assert url == "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC1234567/pdf/"

    def test_resolve_returns_none_when_no_url(self):
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.gateway import resolve_oa_url
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.contracts import (
            OnlineAcquisitionGatewayResult,
        )

        result = OnlineAcquisitionGatewayResult(
            provider="crossref",
            success=True,
            items=[{"title": "No URL paper"}],
            downloads=[],
            warnings=[],
            raw=None,
            meta=None,
            source_trace=[],
        )
        url = resolve_oa_url(result)
        assert url is None


class TestDownloadFileFromUrl:
    @pytest.mark.asyncio
    async def test_download_validates_pdf_magic(self, tmp_path):
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.gateway import download_file_from_url

        with patch("src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.gateway.net_io") as mock_net:
            mock_net.download_file = AsyncMock(return_value={
                "bytes": b"%PDF-1.4 fake content",
                "final_url": "https://example.com/paper.pdf",
                "status_code": 200,
            })
            file_path, final_url, warns = await download_file_from_url(
                "https://example.com/paper.pdf", str(tmp_path), "test_paper"
            )

        assert file_path is not None
        assert file_path.endswith(".pdf")
        assert warns == []

    @pytest.mark.asyncio
    async def test_download_rejects_non_pdf(self, tmp_path):
        """Non-PDF, non-HTML content produces a non_pdf_content warning."""
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.gateway import download_file_from_url

        with patch("src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.gateway.net_io") as mock_net:
            mock_net.download_file = AsyncMock(return_value={
                "bytes": b"Plain text that is not PDF or HTML",
                "final_url": "https://example.com/text.txt",
                "status_code": 200,
            })
            file_path, final_url, warns = await download_file_from_url(
                "https://example.com/text.txt", str(tmp_path), "test_paper"
            )

        assert file_path is None
        assert any("non_pdf" in w for w in warns)

    @pytest.mark.asyncio
    async def test_download_extracts_pdf_from_html(self, tmp_path):
        """When URL returns HTML with a PDF link, it should follow and download."""
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.gateway import download_file_from_url

        call_count = 0

        async def mock_download(url, timeout_ms=30000):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {
                    "bytes": b'<html><a href="https://example.com/paper.pdf">Download</a></html>',
                    "final_url": "https://example.com/article",
                    "status_code": 200,
                }
            else:
                return {
                    "bytes": b"%PDF-1.4 real content",
                    "final_url": url,
                    "status_code": 200,
                }

        with patch("src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.gateway.net_io") as mock_net:
            mock_net.download_file = AsyncMock(side_effect=mock_download)
            file_path, final_url, warns = await download_file_from_url(
                "https://example.com/article", str(tmp_path), "test_paper"
            )

        assert file_path is not None
        assert file_path.endswith(".pdf")
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_download_returns_none_on_html_without_pdf_link(self, tmp_path):
        """HTML page with no PDF links returns None (no file downloaded)."""
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.gateway import download_file_from_url

        with patch("src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.gateway.net_io") as mock_net:
            mock_net.download_file = AsyncMock(return_value={
                "bytes": b"<html>No PDF here</html>",
                "final_url": "https://example.com/page.html",
                "status_code": 200,
            })
            file_path, final_url, warns = await download_file_from_url(
                "https://example.com/page.html", str(tmp_path), "test_paper"
            )

        assert file_path is None

    @pytest.mark.asyncio
    async def test_download_returns_none_on_http_error(self, tmp_path):
        """HTTP 404 returns None with warning."""
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.gateway import download_file_from_url

        with patch("src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.gateway.net_io") as mock_net:
            mock_net.download_file = AsyncMock(return_value={
                "bytes": b"",
                "final_url": "https://example.com/missing.pdf",
                "status_code": 404,
            })
            file_path, final_url, warns = await download_file_from_url(
                "https://example.com/missing.pdf", str(tmp_path), "test_paper"
            )

        assert file_path is None
        assert any("404" in w for w in warns)
