import pytest

from src.domain.literature.gateway.api_gateway import ApiGatewayResult
from src.domain.literature.gateway.web_gateway import WebGatewayResult
from src.domain.literature.unified.workflow import literature_unified_workflow


@pytest.mark.asyncio
async def test_unified_workflow_prefers_api_for_doi(monkeypatch):
    async def fake_api_gateway(request):
        assert request.provider == "unpaywall"
        assert request.identifiers.get("doi") == "10.1000/xyz-123"
        return ApiGatewayResult(
            provider="unpaywall",
            success=True,
            items=[
                {
                    "title": "Example paper",
                    "doi": "10.1000/xyz-123",
                    "journal_name": "Nature",
                    "authors": ["Alice", "Bob"],
                    "year": 2023,
                    "url": "https://example.org/paper",
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
            "prefer": "auto",
            "limit": 5,
            "raw": True,
        }
    )

    assert result["success"] is True
    assert result["route"]["used"] == "api"
    assert result["route"]["api_provider"] == "unpaywall"
    assert result["items"][0]["doi"] == "10.1000/xyz-123"
    assert result["items"][0]["title"] == "Example paper"
    assert "api" in result["raw"]


@pytest.mark.asyncio
async def test_unified_workflow_fallbacks_to_web_when_api_empty(monkeypatch):
    async def fake_api_gateway(request):
        if request.provider == "crossref":
            return ApiGatewayResult(
                provider="crossref",
                success=True,
                items=[],
                warnings=["no_items"],
            )
        return ApiGatewayResult(
            provider=request.provider, success=False, items=[], warnings=[]
        )

    async def fake_auto_web_gateway(request):
        assert request.provider == "pubscholar"
        return WebGatewayResult(
            provider="pubscholar",
            success=True,
            items=[
                {
                    "title": "中文文献",
                    "authors": "张三;李四",
                    "journal": "测试期刊",
                    "year": "2022",
                    "source_link": "https://pubscholar.cn/item/1",
                }
            ],
            warnings=[],
            raw={"provider": "pubscholar"},
        )

    monkeypatch.setattr(
        "src.domain.literature.unified.workflow.call_api_gateway", fake_api_gateway
    )
    monkeypatch.setattr(
        "src.domain.literature.unified.workflow.call_auto_web_gateway",
        fake_auto_web_gateway,
    )

    result = await literature_unified_workflow(
        {
            "query": "肺癌 靶向治疗",
            "prefer": "auto",
            "language": "zh",
            "limit": 3,
        }
    )

    assert result["success"] is True
    assert result["route"]["used"] == "web"
    assert result["route"]["fallback_used"] is True
    assert result["route"]["web_provider"] == "pubscholar"
    assert result["items"][0]["title"] == "中文文献"


@pytest.mark.asyncio
async def test_unified_workflow_respects_prefer_web(monkeypatch):
    async def fake_auto_web_gateway(request):
        assert request.provider == "cyberleninka"
        return WebGatewayResult(
            provider="cyberleninka",
            success=True,
            items=[
                {
                    "title": "Исследование",
                    "authors": "Ivan Ivanov",
                    "journal": "Cyber Journal",
                    "year": "2021",
                    "detail_link": "https://cyberleninka.ru/article/n/test",
                }
            ],
            warnings=[],
            raw={"provider": "cyberleninka"},
        )

    monkeypatch.setattr(
        "src.domain.literature.unified.workflow.call_auto_web_gateway",
        fake_auto_web_gateway,
    )

    result = await literature_unified_workflow(
        {
            "query": "https://cyberleninka.ru/article/n/test",
            "prefer": "web",
            "limit": 2,
        }
    )

    assert result["success"] is True
    assert result["route"]["used"] == "web"
    assert result["route"]["web_provider"] == "cyberleninka"
    assert result["items"][0]["source"] == "cyberleninka"


@pytest.mark.asyncio
async def test_unified_workflow_download_via_api(monkeypatch):
    async def fake_api_gateway(request):
        assert request.action == "download"
        assert request.provider == "unpaywall"
        assert request.download_path == "/tmp/lit-downloads"
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
        }
    )

    assert result["success"] is True
    assert result["route"]["used"] == "api"
    assert len(result["downloads"]) == 1
    assert result["downloads"][0]["file_path"] == "/tmp/lit-downloads/paper.pdf"
    assert result["items"] == []


@pytest.mark.asyncio
async def test_unified_workflow_download_fallback_to_web(monkeypatch):
    async def fake_api_gateway(request):
        return ApiGatewayResult(
            provider=request.provider,
            success=False,
            items=[],
            downloads=[],
            warnings=["crossref_download_unsupported"],
        )

    async def fake_auto_web_gateway(request):
        assert request.action == "download"
        assert request.provider == "pubscholar"
        return WebGatewayResult(
            provider="pubscholar",
            success=True,
            items=[],
            downloads=[
                {
                    "pdf_url": "https://pubscholar.cn/paper.pdf",
                    "file_path": "./downloads/paper.pdf",
                }
            ],
            warnings=[],
            raw={"provider": "pubscholar"},
        )

    monkeypatch.setattr(
        "src.domain.literature.unified.workflow.call_api_gateway", fake_api_gateway
    )
    monkeypatch.setattr(
        "src.domain.literature.unified.workflow.call_auto_web_gateway",
        fake_auto_web_gateway,
    )

    result = await literature_unified_workflow(
        {
            "action": "download",
            "query": "心脑血管 遗传",
            "prefer": "auto",
            "language": "zh",
            "download_path": "./downloads",
        }
    )

    assert result["success"] is True
    assert result["route"]["used"] == "web"
    assert result["route"]["fallback_used"] is True
    assert len(result["downloads"]) == 1
    assert result["downloads"][0]["pdf_url"] == "https://pubscholar.cn/paper.pdf"
