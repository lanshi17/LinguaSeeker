"""Tests for workflow module — with mocked gateway."""

from unittest.mock import AsyncMock, patch

import pytest

from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow import (
    _download_candidates,
    _extract_identifiers,
    online_acquisition_workflow,
)


class TestOnlineAcquisitionExtractIdentifiers:
    def test_doi_extraction(self):
        ids = _extract_identifiers(["10.1234/test.paper"])
        assert ids["doi"] == "10.1234/test.paper"

    def test_pmid_extraction(self):
        ids = _extract_identifiers(["PMID: 12345678"])
        assert ids["pmid"] == "12345678"

    def test_pmcid_extraction(self):
        ids = _extract_identifiers(["PMC12345678"])
        assert ids["pmcid"] == "PMC12345678"

    def test_multiple_identifiers(self):
        ids = _extract_identifiers(["10.1234/test", "PMID: 99999"])
        assert ids["doi"] == "10.1234/test"
        assert ids["pmid"] == "99999"

    def test_no_identifiers(self):
        ids = _extract_identifiers(["just a query"])
        assert ids["doi"] is None
        assert ids["pmid"] is None
        assert ids["pmcid"] is None


class TestOnlineAcquisitionWorkflow:
    @pytest.mark.asyncio
    async def test_invalid_request(self):
        result = await online_acquisition_workflow({"action": "invalid"})
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_search_no_providers(self):
        with (
            patch(
                "src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow.search_provider",
                new_callable=AsyncMock,
            ) as mock_search,
            patch(
                "src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow._acquire_links_firecrawl",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            mock_search.return_value = AsyncMock(
                success=False, items=[], downloads=[], warnings=[], provider="crossref", source_trace=[]
            )
            result = await online_acquisition_workflow({"action": "search", "query": "test"})
            assert "FETCH_NO_RESULT" in str(result.get("warnings"))

    @pytest.mark.asyncio
    async def test_search_returns_candidate_links(self):
        """candidate_links field is populated when search succeeds."""
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

        with (
            patch(
                "src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow.search_provider",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow._acquire_links_firecrawl",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            result = await online_acquisition_workflow({"action": "search", "query": "BRCA1"})

        assert result["success"] is True
        assert len(result["candidate_links"]) > 0

    @pytest.mark.asyncio
    async def test_prefer_web_firecrawl_failure_returns_warning(self):
        """prefer=web handles Firecrawl failure without crashing the workflow."""
        with patch(
            "src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow._acquire_links_firecrawl",
            new_callable=AsyncMock,
            side_effect=RuntimeError("firecrawl down"),
        ):
            result = await online_acquisition_workflow(
                {
                    "action": "search",
                    "query": "BRCA1",
                    "prefer": "web",
                }
            )

        assert result["success"] is False
        assert any("firecrawl acquisition failed" in warning for warning in result["warnings"])
        assert result["route"]["used"] == "web"

    @pytest.mark.asyncio
    async def test_prefer_web_includes_source_trace(self):
        """prefer=web exposes Firecrawl source_trace for debugging."""
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.web_search import (
            SearchLink,
        )

        with patch(
            "src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow._acquire_links_firecrawl",
            new_callable=AsyncMock,
            return_value=[SearchLink(url="https://example.com/paper.pdf", title="Paper")],
        ):
            result = await online_acquisition_workflow(
                {
                    "action": "search",
                    "query": "BRCA1",
                    "prefer": "web",
                }
            )

        assert result["success"] is True
        assert result["raw"]["source_trace"][0]["provider"] == "firecrawl"
        assert result["raw"]["source_trace"][0]["items_count"] == 1


class TestDownloadCandidatesPmcidRouting:
    """PMCID download routing — EuropePMC render first, PMC direct fallback."""

    @pytest.mark.asyncio
    async def test_pmcid_tries_europepmc_render_first(self, tmp_path):
        """EuropePMC render endpoint is tried before the PMC direct URL."""
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.contracts import (
            DownloadResult,
        )

        tried_urls: list[str] = []

        async def fake_download(url, download_path, filename_stem):
            tried_urls.append(url)
            if "europepmc.org/articles" in url:
                return str(tmp_path / "out.pdf"), url, []
            return None, None, []

        with patch(
            "src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow.download_file_from_url",
            new_callable=AsyncMock,
            side_effect=fake_download,
        ):
            downloads = await _download_candidates(
                [{"pmcid": "PMC8440630", "title": "T", "_source_provider": "europepmc"}],
                str(tmp_path),
            )

        assert len(downloads) == 1
        assert isinstance(downloads[0], DownloadResult)
        assert "europepmc.org/articles/PMC8440630" in tried_urls[0]
        # PMC direct URL is NOT tried when EuropePMC render succeeds
        assert not any("ncbi.nlm.nih.gov/pmc" in u for u in tried_urls)

    @pytest.mark.asyncio
    async def test_pmcid_falls_back_to_pmc_direct(self, tmp_path):
        """When EuropePMC render fails, the PMC direct URL is tried."""
        tried_urls: list[str] = []

        async def fake_download(url, download_path, filename_stem):
            tried_urls.append(url)
            if "ncbi.nlm.nih.gov/pmc" in url:
                return str(tmp_path / "out.pdf"), url, []
            return None, None, []

        with patch(
            "src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow.download_file_from_url",
            new_callable=AsyncMock,
            side_effect=fake_download,
        ):
            downloads = await _download_candidates(
                [{"pmcid": "PMC8440630", "title": "T"}],
                str(tmp_path),
            )

        assert len(downloads) == 1
        assert any("europepmc.org/articles/PMC8440630" in u for u in tried_urls)
        assert any("ncbi.nlm.nih.gov/pmc/articles/PMC8440630" in u for u in tried_urls)


class TestDownloadCandidatesDoiRouting:
    """DOI download routing — unpaywall OA resolution."""

    @pytest.mark.asyncio
    async def test_doi_unpaywall_success(self, tmp_path):
        """DOI route calls unpaywall and downloads the resolved OA URL."""
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.contracts import (
            DownloadResult,
            OnlineAcquisitionGatewayResult,
        )

        mock_gateway_result = OnlineAcquisitionGatewayResult(
            provider="unpaywall",
            success=True,
            items=[],
            downloads=[{"pdf_url": "https://oa.example.com/paper.pdf"}],
            warnings=[],
            raw=None,
            meta=None,
            source_trace=[],
        )
        download_calls: list[str] = []

        async def fake_download(url, download_path, filename_stem):
            download_calls.append(url)
            return str(tmp_path / "out.pdf"), url, []

        with (
            patch(
                "src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow.search_provider",
                new_callable=AsyncMock,
                return_value=mock_gateway_result,
            ),
            patch(
                "src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow.download_file_from_url",
                new_callable=AsyncMock,
                side_effect=fake_download,
            ),
        ):
            downloads = await _download_candidates(
                [{"doi": "10.1234/test", "title": "T"}],
                str(tmp_path),
            )

        assert len(downloads) == 1
        assert isinstance(downloads[0], DownloadResult)
        assert downloads[0].source == "unpaywall"
        assert download_calls == ["https://oa.example.com/paper.pdf"]

    @pytest.mark.asyncio
    async def test_doi_unpaywall_no_oa_falls_through_to_pmcid(self, tmp_path):
        """When unpaywall returns no OA URL, PMCID route is tried if available."""
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.contracts import (
            OnlineAcquisitionGatewayResult,
        )

        mock_gateway_result = OnlineAcquisitionGatewayResult(
            provider="unpaywall",
            success=True,
            items=[],
            downloads=[],  # no OA URL
            warnings=["no_oa_location"],
            raw=None,
            meta=None,
            source_trace=[],
        )
        tried_urls: list[str] = []

        async def fake_download(url, download_path, filename_stem):
            tried_urls.append(url)
            if "europepmc.org/articles" in url:
                return str(tmp_path / "out.pdf"), url, []
            return None, None, []

        with (
            patch(
                "src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow.search_provider",
                new_callable=AsyncMock,
                return_value=mock_gateway_result,
            ),
            patch(
                "src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow.download_file_from_url",
                new_callable=AsyncMock,
                side_effect=fake_download,
            ),
        ):
            downloads = await _download_candidates(
                [{"doi": "10.1234/test", "pmcid": "PMC123", "title": "T"}],
                str(tmp_path),
            )

        assert len(downloads) == 1
        assert downloads[0].source == "pmc"
        assert any("europepmc.org/articles/PMC123" in u for u in tried_urls)

    @pytest.mark.asyncio
    async def test_doi_unpaywall_exception_falls_through_to_url(self, tmp_path):
        """An unpaywall exception is caught; download continues to direct URL route."""

        async def fake_download(url, download_path, filename_stem):
            return str(tmp_path / "out.pdf"), url, []

        with (
            patch(
                "src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow.search_provider",
                new_callable=AsyncMock,
                side_effect=RuntimeError("unpaywall down"),
            ),
            patch(
                "src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow.download_file_from_url",
                new_callable=AsyncMock,
                side_effect=fake_download,
            ),
        ):
            downloads = await _download_candidates(
                [{"doi": "10.1234/test", "url": "https://example.com/paper.pdf", "title": "T"}],
                str(tmp_path),
            )

        # Falls through to direct URL route
        assert len(downloads) == 1
        assert downloads[0].source == "direct"


class TestDownloadCandidatesDirectUrlRouting:
    """Direct URL download routing — route 3."""

    @pytest.mark.asyncio
    async def test_direct_url_download(self, tmp_path):
        """Candidate with only a URL downloads via the direct route."""
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.contracts import (
            DownloadResult,
        )

        async def fake_download(url, download_path, filename_stem):
            if url == "https://example.com/paper.pdf":
                return str(tmp_path / "out.pdf"), url, []
            return None, None, []

        with patch(
            "src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow.download_file_from_url",
            new_callable=AsyncMock,
            side_effect=fake_download,
        ):
            downloads = await _download_candidates(
                [{"url": "https://example.com/paper.pdf", "title": "T", "_source_provider": "crossref"}],
                str(tmp_path),
            )

        assert len(downloads) == 1
        assert isinstance(downloads[0], DownloadResult)
        assert downloads[0].source == "crossref"

    @pytest.mark.asyncio
    async def test_no_identifiers_no_download(self, tmp_path):
        """Candidate with no DOI/PMCID/URL produces no downloads."""

        async def fake_download(url, download_path, filename_stem):
            return str(tmp_path / "out.pdf"), url, []

        with patch(
            "src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow.download_file_from_url",
            new_callable=AsyncMock,
            side_effect=fake_download,
        ):
            downloads = await _download_candidates(
                [{"title": "T"}],
                str(tmp_path),
            )

        assert downloads == []
