import pytest

from src.domain.literature.gateway.api_gateway import ApiGatewayResult
from src.domain.literature.unified.workflow import literature_unified_workflow


@pytest.mark.asyncio
async def test_selects_crossref_for_doi_search_and_records_source_trace(monkeypatch):
    calls = []

    async def fake_api_gateway(request):
        calls.append(request)
        return ApiGatewayResult(
            provider="crossref",
            success=True,
            items=[
                {
                    "title": "Crossref result",
                    "doi": "10.1000/xyz-123",
                    "journal": "Nature",
                    "year": "2024",
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

    assert len(calls) == 1
    assert calls[0].provider == "crossref"
    assert result["success"] is True
    assert result["route"]["api_provider"] == "crossref"
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
async def test_retries_provider_on_transient_failure_and_records_attempts(monkeypatch):
    call_count = 0

    async def flaky_api_gateway(request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("transient upstream error")
        return ApiGatewayResult(
            provider="crossref",
            success=True,
            items=[
                {
                    "title": "Recovered result",
                    "doi": "10.1000/xyz-123",
                }
            ],
            warnings=["retry_success"],
            raw={"provider": "crossref"},
        )

    monkeypatch.setattr(
        "src.domain.literature.unified.workflow.call_api_gateway", flaky_api_gateway
    )

    result = await literature_unified_workflow(
        {
            "query": "10.1000/xyz-123",
            "prefer": "auto",
            "limit": 5,
            "raw": True,
        }
    )

    assert call_count == 2
    assert result["success"] is True
    assert result["route"]["api_provider"] == "crossref"
    assert result["raw"]["api"]["source_trace"] == [
        {
            "provider": "crossref",
            "attempt": 1,
            "success": False,
            "items_count": 0,
            "downloads_count": 0,
            "warnings": [],
            "error": "transient upstream error",
        },
        {
            "provider": "crossref",
            "attempt": 2,
            "success": True,
            "items_count": 1,
            "downloads_count": 0,
            "warnings": ["retry_success"],
            "error": None,
        },
    ]


@pytest.mark.asyncio
async def test_download_prefers_unpaywall_for_doi_download_and_trace_recorded(
    monkeypatch,
):
    calls = []

    async def fake_api_gateway(request):
        calls.append(request)
        return ApiGatewayResult(
            provider="unpaywall",
            success=True,
            items=[],
            downloads=[
                {
                    "pdf_url": "https://example.org/paper.pdf",
                    "file_path": "/tmp/lit-downloads/paper.pdf",
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
            "action": "download",
            "query": "10.1000/xyz-123",
            "prefer": "auto",
            "download_path": "/tmp/lit-downloads",
            "raw": True,
        }
    )

    assert len(calls) == 1
    assert calls[0].provider == "unpaywall"
    assert result["success"] is True
    assert result["route"]["api_provider"] == "unpaywall"
    assert result["raw"]["api"]["source_trace"] == [
        {
            "provider": "unpaywall",
            "attempt": 1,
            "success": True,
            "items_count": 0,
            "downloads_count": 1,
            "warnings": [],
            "error": None,
        }
    ]
