import pytest

from src.domain.literature.gateway.api_gateway import ApiGatewayResult
from src.domain.literature.unified.workflow import literature_unified_workflow


@pytest.mark.asyncio
async def test_unified_workflow_routes_to_pmc_for_doi(monkeypatch):
    async def fake_api_gateway(request):
        assert request.provider == "pmc"
        assert request.identifiers.get("doi") == "10.1000/xyz-123"
        return ApiGatewayResult(
            provider="pmc",
            success=True,
            items=[
                {
                    "title": "Example paper",
                    "pmcid": "PMC1234567",
                    "doi": "10.1000/xyz-123",
                    "journal_title": "Nature",
                    "year": "2023",
                    "authors": ["Alice", "Bob"],
                    "url": "https://example.org/paper",
                }
            ],
            warnings=[],
            raw={"provider": "pmc"},
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
    assert result["route"]["api_provider"] == "pmc"
    assert result["items"][0]["doi"] == "10.1000/xyz-123"
    assert result["items"][0]["title"] == "Example paper"
    assert "api" in result["raw"]


@pytest.mark.asyncio
async def test_unified_workflow_rejects_prefer_web_in_mvp():
    result = await literature_unified_workflow(
        {
            "query": "https://cyberleninka.ru/article/n/test",
            "prefer": "web",
            "limit": 2,
        }
    )

    assert result["success"] is False
    assert result["route"]["used"] == "none"
    assert result["route"]["reason"] == "mvp_pubmed_only"
    assert "INPUT_INVALID: web source is disabled in MVP" in result["warnings"]


@pytest.mark.asyncio
async def test_unified_workflow_rejects_non_pmc_api_provider():
    result = await literature_unified_workflow(
        {
            "query": "10.1000/xyz-123",
            "prefer": "api",
            "api_provider": "unpaywall",
        }
    )

    assert result["success"] is False
    assert result["route"]["used"] == "none"
    assert result["route"]["reason"] == "mvp_pubmed_only"
    assert (
        "INPUT_INVALID: api_provider 'unpaywall' is disabled in MVP"
        in result["warnings"]
    )


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
