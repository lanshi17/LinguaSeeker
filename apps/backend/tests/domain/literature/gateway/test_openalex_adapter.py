import pytest

from src.domain.literature.gateway.contracts import ApiGatewayRequest, ApiGatewayResult
from src.domain.literature.gateway.adapters.openalex_adapter import OpenAlexAdapter


@pytest.mark.asyncio
async def test_openalex_adapter_routes_search_through_existing_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_call_openalex(
        query: str | None,
        doi: str | None,
        limit: int,
        raw: bool,
        api_params: dict[str, str] | None = None,
    ) -> ApiGatewayResult:
        assert query == "breast cancer"
        assert doi is None
        assert limit == 4
        assert raw is True
        assert api_params == {}
        return ApiGatewayResult(
            provider="openalex",
            success=True,
            items=[{"doi": "10.1000/openalex-1", "title": "Open Access article"}],
            warnings=["openalex-warning"],
            raw={"provider": "openalex"},
            meta={"total": 1},
        )

    monkeypatch.setattr(
        "src.domain.literature.gateway.adapters.openalex_adapter.call_openalex",
        fake_call_openalex,
    )

    adapter = OpenAlexAdapter()
    result = await adapter.execute(
        ApiGatewayRequest(
            provider="openalex",
            action="search",
            query="breast cancer",
            limit=4,
            raw=True,
            params={},
        )
    )

    assert result.provider == "openalex"
    assert result.success is True
    assert result.items == [{"doi": "10.1000/openalex-1", "title": "Open Access article"}]
    assert result.warnings == ["openalex-warning"]
    assert result.raw == {"provider": "openalex"}
    assert result.meta == {"total": 1}


@pytest.mark.asyncio
async def test_openalex_adapter_routes_download_through_existing_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_call_openalex_download(
        query: str | None,
        doi: str | None,
        limit: int,
        raw: bool,
        download_path: str,
        selected_index: int,
        api_params: dict[str, str] | None = None,
    ) -> ApiGatewayResult:
        assert query is None
        assert doi == "10.1000/openalex-1"
        assert limit == 1
        assert raw is False
        assert download_path == "./test-downloads"
        assert selected_index == 0
        assert api_params == {}
        return ApiGatewayResult(
            provider="openalex",
            success=True,
            items=[],
            downloads=[{"pdf_url": "https://example.com/test.pdf", "file_path": "./test-downloads/test.pdf"}],
            warnings=[],
            raw=None,
            meta=None,
        )

    monkeypatch.setattr(
        "src.domain.literature.gateway.adapters.openalex_adapter.call_openalex_download",
        fake_call_openalex_download,
    )

    adapter = OpenAlexAdapter()
    result = await adapter.execute(
        ApiGatewayRequest(
            provider="openalex",
            action="download",
            query=None,
            identifiers={"doi": "10.1000/openalex-1"},
            limit=1,
            raw=False,
            download_path="./test-downloads",
            selected_index=0,
            params={},
        )
    )

    assert result.provider == "openalex"
    assert result.success is True
    assert result.downloads == [{"pdf_url": "https://example.com/test.pdf", "file_path": "./test-downloads/test.pdf"}]
