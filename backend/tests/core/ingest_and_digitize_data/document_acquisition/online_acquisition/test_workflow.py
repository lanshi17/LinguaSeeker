"""Tests for workflow module — with mocked gateway."""

from unittest.mock import AsyncMock, patch

import pytest

from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow import (
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
        with patch(
            "src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow.search_provider",
            new_callable=AsyncMock,
        ) as mock_search, patch(
            "src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow._acquire_links_firecrawl",
            new_callable=AsyncMock,
            return_value=[],
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

        with patch(
            "src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow.search_provider",
            new_callable=AsyncMock,
            return_value=mock_result,
        ), patch(
            "src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow._acquire_links_firecrawl",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await online_acquisition_workflow({"action": "search", "query": "BRCA1"})

        assert result["success"] is True
        assert len(result["candidate_links"]) > 0
