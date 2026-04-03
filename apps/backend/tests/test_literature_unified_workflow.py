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
async def test_unified_workflow_routes_prefer_web_through_web_gateway(monkeypatch):
    async def fake_web_gateway(request):
        assert request.provider == "pubscholar"
        assert request.action == "search"
        assert request.query == "LDLR variant evidence"
        return WebGatewayResult(
            provider="pubscholar",
            success=True,
            items=[
                {
                    "title": "Web article",
                    "url": "https://example.org/web-article",
                    "journal": "Web Journal",
                    "year": "2024",
                }
            ],
            warnings=[],
            downloads=[],
            raw={"provider": "pubscholar"},
        )

    monkeypatch.setattr(
        "src.domain.literature.unified.workflow.call_auto_web_gateway", fake_web_gateway
    )

    result = await literature_unified_workflow(
        {
            "query": "LDLR variant evidence",
            "prefer": "web",
            "web_provider": "pubscholar",
            "limit": 3,
            "raw": True,
        }
    )

    assert result["success"] is True
    assert result["route"]["used"] == "web"
    assert result["route"]["web_provider"] == "pubscholar"
    assert result["items"][0]["title"] == "Web article"
    assert result["raw"]["web"]["provider"] == "pubscholar"


@pytest.mark.asyncio
async def test_unified_workflow_defaults_to_pubscholar_for_prefer_web(monkeypatch):
    async def fake_web_gateway(request):
        assert request.provider == "pubscholar"
        assert request.action == "search"
        assert request.query == "https://cyberleninka.ru/article/n/test"
        return WebGatewayResult(
            provider="pubscholar",
            success=False,
            items=[],
            warnings=["web_no_items"],
            downloads=[],
            raw={"provider": "pubscholar"},
        )

    monkeypatch.setattr(
        "src.domain.literature.unified.workflow.call_auto_web_gateway", fake_web_gateway
    )

    result = await literature_unified_workflow(
        {
            "query": "https://cyberleninka.ru/article/n/test",
            "prefer": "web",
            "limit": 2,
            "raw": True,
        }
    )

    assert result["success"] is False
    assert result["route"]["used"] == "web"
    assert result["route"]["web_provider"] == "pubscholar"
    assert result["route"]["reason"] == "web_no_items"
    assert "FETCH_NO_RESULT" in result["warnings"]
    assert result["raw"]["web"]["provider"] == "pubscholar"


@pytest.mark.asyncio
async def test_unified_workflow_routes_explicit_non_pmc_api_provider(monkeypatch):
    async def fake_api_gateway(request):
        assert request.provider == "unpaywall"
        assert request.action == "search"
        assert request.query == "10.1000/xyz-123"
        return ApiGatewayResult(
            provider="unpaywall",
            success=True,
            items=[
                {
                    "title": "Open article",
                    "doi": "10.1000/xyz-123",
                    "journal": "Open Journal",
                    "year": "2024",
                    "url": "https://example.org/open-article",
                }
            ],
            warnings=[],
            raw={"provider": "unpaywall"},
        )

    monkeypatch.setattr(
        "src.domain.literature.unified.workflow.call_api_gateway", fake_api_gateway
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
    assert result["items"][0]["title"] == "Open article"
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
async def test_unified_workflow_falls_back_to_web_when_api_has_no_items(monkeypatch):
    async def fake_api_gateway(request):
        assert request.provider == "pmc"
        return ApiGatewayResult(
            provider="pmc",
            success=True,
            items=[],
            warnings=["api-no-items"],
            raw={"provider": "pmc"},
        )

    async def fake_web_gateway(request):
        assert request.provider == "pubscholar"
        assert request.action == "search"
        assert request.query == "LDLR evidence"
        return WebGatewayResult(
            provider="pubscholar",
            success=True,
            items=[
                {
                    "title": "Fallback web article",
                    "url": "https://example.org/fallback-web-article",
                    "journal": "Web Journal",
                    "year": "2024",
                }
            ],
            warnings=["web-fallback"],
            downloads=[],
            raw={"provider": "pubscholar"},
        )

    monkeypatch.setattr(
        "src.domain.literature.unified.workflow.call_api_gateway", fake_api_gateway
    )
    monkeypatch.setattr(
        "src.domain.literature.unified.workflow.call_auto_web_gateway", fake_web_gateway
    )

    result = await literature_unified_workflow(
        {
            "query": "LDLR evidence",
            "prefer": "auto",
            "limit": 5,
            "raw": True,
        }
    )

    assert result["success"] is True
    assert result["route"]["used"] == "web"
    assert result["route"]["api_provider"] == "pmc"
    assert result["route"]["web_provider"] == "pubscholar"
    assert result["route"]["fallback_used"] is True
    assert result["items"][0]["title"] == "Fallback web article"
    assert result["raw"]["api"]["raw"]["provider"] == "pmc"
    assert result["raw"]["web"]["provider"] == "pubscholar"


@pytest.mark.asyncio
async def test_unified_workflow_retries_web_provider_and_records_trace(monkeypatch):
    call_count = 0

    async def flaky_web_gateway(request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("transient web error")
        return WebGatewayResult(
            provider="pubscholar",
            success=True,
            items=[
                {
                    "title": "Recovered web article",
                    "url": "https://example.org/recovered-web-article",
                    "journal": "Web Journal",
                    "year": "2024",
                }
            ],
            warnings=["web-retry-success"],
            downloads=[],
            raw={"provider": "pubscholar"},
        )

    monkeypatch.setattr(
        "src.domain.literature.unified.workflow.call_auto_web_gateway", flaky_web_gateway
    )

    result = await literature_unified_workflow(
        {
            "query": "LDLR evidence",
            "prefer": "web",
            "web_provider": "pubscholar",
            "limit": 3,
            "raw": True,
        }
    )

    assert call_count == 2
    assert result["success"] is True
    assert result["route"]["used"] == "web"
    assert result["raw"]["web"]["source_trace"] == [
        {
            "provider": "pubscholar",
            "attempt": 1,
            "success": False,
            "items_count": 0,
            "downloads_count": 0,
            "warnings": [],
            "error": "transient web error",
        },
        {
            "provider": "pubscholar",
            "attempt": 2,
            "success": True,
            "items_count": 1,
            "downloads_count": 0,
            "warnings": ["web-retry-success"],
            "error": None,
        },
    ]


@pytest.mark.asyncio
async def test_unified_workflow_auto_uses_explicit_web_provider_for_fallback(monkeypatch):
    async def fake_api_gateway(request):
        assert request.provider == "pmc"
        return ApiGatewayResult(
            provider="pmc",
            success=True,
            items=[],
            warnings=["api-no-items"],
            raw={"provider": "pmc"},
        )

    async def fake_web_gateway(request):
        assert request.provider == "cyberleninka"
        assert request.action == "search"
        assert request.query == "LDLR evidence"
        return WebGatewayResult(
            provider="cyberleninka",
            success=True,
            items=[
                {
                    "title": "Cyberleninka fallback article",
                    "url": "https://cyberleninka.ru/article/n/example",
                    "journal": "Cyber Journal",
                    "year": "2024",
                }
            ],
            warnings=["web-fallback"],
            downloads=[],
            raw={"provider": "cyberleninka"},
        )

    monkeypatch.setattr(
        "src.domain.literature.unified.workflow.call_api_gateway", fake_api_gateway
    )
    monkeypatch.setattr(
        "src.domain.literature.unified.workflow.call_auto_web_gateway", fake_web_gateway
    )

    result = await literature_unified_workflow(
        {
            "query": "LDLR evidence",
            "prefer": "auto",
            "web_provider": "cyberleninka",
            "limit": 5,
            "raw": True,
        }
    )

    assert result["success"] is True
    assert result["route"]["used"] == "web"
    assert result["route"]["api_provider"] == "pmc"
    assert result["route"]["web_provider"] == "cyberleninka"
    assert result["route"]["fallback_used"] is True
    assert result["items"][0]["title"] == "Cyberleninka fallback article"
    assert result["raw"]["api"]["raw"]["provider"] == "pmc"
    assert result["raw"]["web"]["provider"] == "cyberleninka"


@pytest.mark.asyncio
async def test_unified_workflow_download_falls_back_to_web_when_api_has_no_file(monkeypatch):
    async def fake_api_gateway(request):
        assert request.action == "download"
        assert request.provider == "pmc"
        return ApiGatewayResult(
            provider="pmc",
            success=True,
            items=[],
            downloads=[],
            warnings=["api-download-empty"],
            raw={"provider": "pmc"},
        )

    async def fake_web_gateway(request):
        assert request.action == "download"
        assert request.provider == "pubscholar"
        assert request.download_path == "/tmp/lit-downloads"
        return WebGatewayResult(
            provider="pubscholar",
            success=True,
            items=[],
            warnings=["web-download-fallback"],
            downloads=[
                {
                    "pdf_url": "https://example.org/fallback.pdf",
                    "file_path": "/tmp/lit-downloads/fallback.pdf",
                }
            ],
            raw={"provider": "pubscholar"},
        )

    monkeypatch.setattr(
        "src.domain.literature.unified.workflow.call_api_gateway", fake_api_gateway
    )
    monkeypatch.setattr(
        "src.domain.literature.unified.workflow.call_auto_web_gateway", fake_web_gateway
    )

    result = await literature_unified_workflow(
        {
            "action": "download",
            "query": "PMID:12345678",
            "prefer": "auto",
            "download_path": "/tmp/lit-downloads",
            "raw": True,
        }
    )

    assert result["success"] is True
    assert result["route"]["used"] == "web"
    assert result["route"]["api_provider"] == "pmc"
    assert result["route"]["web_provider"] == "pubscholar"
    assert result["route"]["fallback_used"] is True
    assert result["downloads"][0]["file_path"] == "/tmp/lit-downloads/fallback.pdf"
    assert result["raw"]["api"]["raw"]["provider"] == "pmc"
    assert result["raw"]["web"]["provider"] == "pubscholar"


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
