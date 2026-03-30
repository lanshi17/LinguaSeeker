import pytest

from src.domain.literature.gateway.contracts import ApiGatewayRequest, ApiGatewayResult
from src.domain.literature.gateway.adapters.unpaywall_adapter import UnpaywallAdapter


@pytest.mark.asyncio
async def test_unpaywall_adapter_routes_search_through_existing_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_call_unpaywall(
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
        assert api_params == {"email": "tests@example.org"}
        return ApiGatewayResult(
            provider="unpaywall",
            success=True,
            items=[{"doi": "10.1000/unpaywall-1", "title": "Open article"}],
            warnings=["unpaywall-warning"],
            raw={"provider": "unpaywall"},
            meta={"total": 1},
        )

    monkeypatch.setattr(
        "src.domain.literature.gateway.adapters.unpaywall_adapter.call_unpaywall",
        fake_call_unpaywall,
    )

    adapter = UnpaywallAdapter()
    result = await adapter.execute(
        ApiGatewayRequest(
            provider="unpaywall",
            action="search",
            query="breast cancer",
            limit=4,
            raw=True,
            params={"email": "tests@example.org"},
        )
    )

    assert result.provider == "unpaywall"
    assert result.success is True
    assert result.items == [{"doi": "10.1000/unpaywall-1", "title": "Open article"}]
    assert result.warnings == ["unpaywall-warning"]
    assert result.raw == {"provider": "unpaywall"}
    assert result.meta == {"total": 1}
