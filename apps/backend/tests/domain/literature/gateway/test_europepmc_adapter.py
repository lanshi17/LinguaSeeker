import pytest

from src.domain.literature.gateway.contracts import ApiGatewayRequest, ApiGatewayResult
from src.domain.literature.gateway.adapters.europepmc_adapter import EuropePmcAdapter


@pytest.mark.asyncio
async def test_europepmc_adapter_routes_search_through_existing_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_call_europepmc(
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
            provider="europepmc",
            success=True,
            items=[{"doi": "10.1000/europepmc-1", "title": "Open Access article"}],
            warnings=["europepmc-warning"],
            raw={"provider": "europepmc"},
            meta={"total": 1},
        )

    monkeypatch.setattr(
        "src.domain.literature.gateway.adapters.europepmc_adapter.call_europepmc",
        fake_call_europepmc,
    )

    adapter = EuropePmcAdapter()
    result = await adapter.execute(
        ApiGatewayRequest(
            provider="europepmc",
            action="search",
            query="breast cancer",
            limit=4,
            raw=True,
            params={},
        )
    )

    assert result.provider == "europepmc"
    assert result.success is True
    assert result.items == [{"doi": "10.1000/europepmc-1", "title": "Open Access article"}]
    assert result.warnings == ["europepmc-warning"]
    assert result.raw == {"provider": "europepmc"}
    assert result.meta == {"total": 1}


@pytest.mark.asyncio
async def test_europepmc_adapter_routes_download_through_existing_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_call_europepmc_download(
        query: str | None,
        doi: str | None,
        limit: int,
        raw: bool,
        download_path: str,
        selected_index: int,
        api_params: dict[str, str] | None = None,
    ) -> ApiGatewayResult:
        assert query is None
        assert doi == "10.1000/europepmc-1"
        assert limit == 1
        assert raw is False
        assert download_path == "./test-downloads"
        assert selected_index == 0
        assert api_params == {}
        return ApiGatewayResult(
            provider="europepmc",
            success=True,
            items=[],
            downloads=[{"pdf_url": "https://europepmc.org/test.pdf", "file_path": "./test-downloads/test.pdf"}],
            warnings=[],
            raw=None,
            meta=None,
        )

    monkeypatch.setattr(
        "src.domain.literature.gateway.adapters.europepmc_adapter.call_europepmc_download",
        fake_call_europepmc_download,
    )

    adapter = EuropePmcAdapter()
    result = await adapter.execute(
        ApiGatewayRequest(
            provider="europepmc",
            action="download",
            query=None,
            identifiers={"doi": "10.1000/europepmc-1"},
            limit=1,
            raw=False,
            download_path="./test-downloads",
            selected_index=0,
            params={},
        )
    )

    assert result.provider == "europepmc"
    assert result.success is True
    assert result.downloads == [{"pdf_url": "https://europepmc.org/test.pdf", "file_path": "./test-downloads/test.pdf"}]
