import pytest

from src.domain.literature.gateway.api_gateway import ApiGatewayResult
from src.domain.literature.gateway.web_gateway import WebGatewayResult
from src.domain.literature.unified.workflow import literature_unified_workflow


@pytest.mark.asyncio
async def test_unified_workflow_routes_to_crossref_for_doi(monkeypatch):
    async def fake_api_gateway(request):
        assert request.provider == "crossref"
        assert request.identifiers.get("doi") == "10.1000/xyz-123"
        return ApiGatewayResult(
            provider="crossref",
            success=True,
            items=[
                {
                    "title": "Example paper",
                    "doi": "10.1000/xyz-123",
                    "journal_title": "Nature",
                    "year": "2023",
                    "authors": ["Alice", "Bob"],
                    "url": "https://example.org/paper",
                }
            ],
            warnings=[],
            raw={"provider": "crossref"},
        )

    monkeypatch.setattr(
        "src.domain.literature.unified.workflow.call_api_gateway", fake_api_gateway
    )

    result = await literature_unified_workflow(
        {
            "query": "10.1000/xyz-123",
            "prefer": "auto",
            "limit": 5,
            "raw": True,
        }
    )

    assert result["success"] is True
    assert result["route"]["used"] == "api"
    assert result["route"]["api_provider"] == "crossref"
    assert result["items"][0]["title"] == "Example paper"
    assert result["items"][0]["doi"] == "10.1000/xyz-123"
    assert result["raw"]["api"]["source_trace"] == [
        {
            "provider": "crossref",
            "attempt": 1,
            "success": True,
            "items_count": 1,
            "downloads_count": 0,
            "warnings": [],
            "error": None,
        }
    ]


@pytest.mark.asyncio
async def test_unified_workflow_routes_to_web_provider_when_requested(monkeypatch):
    async def fake_web_gateway(request):
        assert request.provider == "cyberleninka"
        assert request.action == "search"
        assert request.query == "https://cyberleninka.ru/article/n/test"
        return WebGatewayResult(
            provider="cyberleninka",
            success=True,
            items=[
                {
                    "title": "Cyberleninka result",
                    "url": "https://cyberleninka.ru/article/n/test",
                    "authors": ["Alice"],
                    "journal": "Cyberleninka Journal",
                    "year": "2024",
                }
            ],
            warnings=[],
            raw={"provider": "cyberleninka"},
        )

    monkeypatch.setattr(
        "src.domain.literature.unified.workflow.call_auto_web_gateway",
        fake_web_gateway,
    )

    result = await literature_unified_workflow(
        {
            "query": "https://cyberleninka.ru/article/n/test",
            "prefer": "web",
            "web_provider": "cyberleninka",
            "limit": 2,
            "raw": True,
        }
    )

    assert result["success"] is True
    assert result["route"]["used"] == "web"
    assert result["route"]["web_provider"] == "cyberleninka"
    assert result["route"]["reason"] == "web_provider:cyberleninka"
    assert result["items"][0]["title"] == "Cyberleninka result"
    assert result["raw"]["web"]["source_trace"] == [
        {
            "provider": "cyberleninka",
            "attempt": 1,
            "success": True,
            "items_count": 1,
            "downloads_count": 0,
            "warnings": [],
            "error": None,
        }
    ]


@pytest.mark.asyncio
async def test_unified_workflow_allows_explicit_non_pmc_api_provider(monkeypatch):
    async def fake_api_gateway(request):
        assert request.provider == "unpaywall"
        assert request.query == "10.1000/xyz-123"
        return ApiGatewayResult(
            provider="unpaywall",
            success=True,
            items=[
                {
                    "title": "Open result",
                    "doi": "10.1000/xyz-123",
                    "journal_title": "Open Journal",
                    "year": "2024",
                    "authors": ["Alice"],
                    "best_oa_location": {"url": "https://example.org/paper"},
                }
            ],
            warnings=[],
            raw={"provider": "unpaywall"},
        )

    monkeypatch.setattr(
        "src.domain.literature.unified.workflow.call_api_gateway",
        fake_api_gateway,
    )

    result = await literature_unified_workflow(
        {
            "query": "10.1000/xyz-123",
            "prefer": "api",
            "api_provider": "unpaywall",
            "raw": True,
        }
    )

    assert result["success"] is True
    assert result["route"]["used"] == "api"
    assert result["route"]["api_provider"] == "unpaywall"
    assert result["route"]["reason"] == "api_provider:unpaywall"
    assert result["items"][0]["doi"] == "10.1000/xyz-123"
    assert result["raw"]["api"]["source_trace"] == [
        {
            "provider": "unpaywall",
            "attempt": 1,
            "success": True,
            "items_count": 1,
            "downloads_count": 0,
            "warnings": [],
            "error": None,
        }
    ]


@pytest.mark.asyncio
async def test_unified_workflow_download_via_pmc(monkeypatch):
    async def fake_api_gateway(request):
        assert request.action == "download"
        assert request.provider == "pmc"
        assert request.download_path == "/tmp/lit-downloads"
        return ApiGatewayResult(
            provider="pmc",
            success=True,
            items=[],
            downloads=[
                {
                    "pdf_url": "https://example.org/paper.pdf",
                    "file_path": "/tmp/lit-downloads/paper.pdf",
                }
            ],
            warnings=[],
        )

    monkeypatch.setattr(
        "src.domain.literature.unified.workflow.call_api_gateway", fake_api_gateway
    )

    result = await literature_unified_workflow(
        {
            "action": "download",
            "query": "PMID:12345678",
            "prefer": "auto",
            "download_path": "/tmp/lit-downloads",
        }
    )

    assert result["success"] is True
    assert result["route"]["used"] == "api"
    assert result["route"]["api_provider"] == "pmc"
    assert len(result["downloads"]) == 1
    assert result["downloads"][0]["file_path"] == "/tmp/lit-downloads/paper.pdf"
    assert result["items"] == []


@pytest.mark.asyncio
async def test_unified_workflow_passes_download_selection_fields_to_gateway(
    monkeypatch,
):
    async def fake_api_gateway(request):
        assert request.action == "download"
        assert request.provider == "pmc"
        assert request.download_path == "/tmp/downloads"
        assert request.selected_index == 2
        assert request.selected_title == "Chosen article"
        assert (
            request.detail_link == "https://pmc.ncbi.nlm.nih.gov/articles/PMC1234567/"
        )
        return ApiGatewayResult(
            provider="pmc",
            success=True,
            items=[],
            downloads=[
                {
                    "pdf_url": "https://example.org/paper.pdf",
                    "file_path": "/tmp/downloads/chosen.pdf",
                }
            ],
            warnings=[],
        )

    monkeypatch.setattr(
        "src.domain.literature.unified.workflow.call_api_gateway", fake_api_gateway
    )

    result = await literature_unified_workflow(
        {
            "action": "download",
            "query": "PMID:12345678",
            "prefer": "auto",
            "download_path": "/tmp/downloads",
            "selected_index": 2,
            "selected_title": "Chosen article",
            "detail_link": "https://pmc.ncbi.nlm.nih.gov/articles/PMC1234567/",
        }
    )

    assert result["success"] is True
    assert result["route"]["used"] == "api"
    assert result["route"]["api_provider"] == "pmc"
    assert result["downloads"][0]["file_path"] == "/tmp/downloads/chosen.pdf"


@pytest.mark.asyncio
async def test_unified_workflow_download_without_file_returns_failure(monkeypatch):
    async def fake_api_gateway(request):
        return ApiGatewayResult(
            provider="pmc",
            success=True,
            items=[],
            downloads=[],
            warnings=[],
        )

    monkeypatch.setattr(
        "src.domain.literature.unified.workflow.call_api_gateway", fake_api_gateway
    )

    result = await literature_unified_workflow(
        {
            "action": "download",
            "query": "PMID:12345678",
            "prefer": "auto",
            "download_path": "./downloads",
        }
    )

    assert result["success"] is False
    assert result["route"]["used"] == "api"
    assert result["route"]["reason"] == "api_download_failed"
    assert "FULLTEXT_UNAVAILABLE" in result["warnings"]
