"""Tests for workflow module — with mocked gateway."""

from unittest.mock import AsyncMock, patch

import pytest

from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow import (
    _build_provider_chain,
    _extract_identifiers,
    _select_initial_provider,
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


class TestSelectInitialProvider:
    def test_doi_search(self):
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.contracts import OnlineAcquisitionRequest
        req = OnlineAcquisitionRequest(action="search")
        ids = {"doi": "10.1234/test", "pmcid": None, "pmid": None}
        assert _select_initial_provider(req, ids) == "crossref"

    def test_doi_download(self):
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.contracts import OnlineAcquisitionRequest
        req = OnlineAcquisitionRequest(action="download")
        ids = {"doi": "10.1234/test", "pmcid": None, "pmid": None}
        assert _select_initial_provider(req, ids) == "unpaywall"

    def test_pmid(self):
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.contracts import OnlineAcquisitionRequest
        req = OnlineAcquisitionRequest()
        ids = {"doi": None, "pmcid": None, "pmid": "12345"}
        assert _select_initial_provider(req, ids) == "pmc"

    def test_explicit_provider(self):
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.contracts import OnlineAcquisitionRequest
        req = OnlineAcquisitionRequest(api_provider="doaj")
        ids = {"doi": None, "pmcid": None, "pmid": None}
        assert _select_initial_provider(req, ids) == "doaj"


class TestBuildProviderChain:
    def test_doi_chain(self):
        ids = {"doi": "10.1234/test", "pmcid": None, "pmid": None}
        chain = _build_provider_chain(ids)
        assert "crossref" in chain
        assert "unpaywall" in chain

    def test_pmid_chain(self):
        ids = {"doi": None, "pmcid": None, "pmid": "12345"}
        chain = _build_provider_chain(ids)
        assert chain == ["pmc"]

    def test_default_chain(self):
        ids = {"doi": None, "pmcid": None, "pmid": None}
        chain = _build_provider_chain(ids)
        assert "crossref" in chain


class TestOnlineAcquisitionWorkflow:
    @pytest.mark.asyncio
    async def test_invalid_request(self):
        result = await online_acquisition_workflow({"action": "invalid"})
        assert result["success"] is False
        assert "invalid_request" in result["warnings"][0]

    @pytest.mark.asyncio
    async def test_web_without_provider(self):
        result = await online_acquisition_workflow({"action": "search", "prefer": "web"})
        assert result["success"] is False
        assert "web_provider" in result["warnings"][0]

    @pytest.mark.asyncio
    async def test_search_no_providers(self):
        with patch(
            "src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow.search_provider",
            new_callable=AsyncMock,
        ) as mock_search:
            mock_search.return_value = AsyncMock(
                success=False, items=[], downloads=[], warnings=[], provider="crossref", source_trace=[]
            )
            result = await online_acquisition_workflow({"action": "search", "query": "test"})
            assert "FETCH_NO_RESULT" in str(result.get("warnings"))
