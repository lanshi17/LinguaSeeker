import pytest

from src.domain.literature.gateway.contracts import ApiGatewayRequest, ApiGatewayResult
from src.domain.literature.gateway.adapters.crossref_adapter import CrossrefAdapter


@pytest.mark.asyncio
async def test_crossref_adapter_routes_search_through_existing_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_call_crossref(
        query: str | None,
        limit: int,
        raw: bool,
        filter_expr: str | None = None,
        api_params: dict[str, str] | None = None,
    ) -> ApiGatewayResult:
        assert query == "ldlr"
        assert limit == 7
        assert raw is True
        assert filter_expr == "doi:10.1000/xyz-123"
        assert api_params == {"mailto": "tests@example.org"}
        return ApiGatewayResult(
            provider="crossref",
            success=True,
            items=[{"doi": "10.1000/xyz-123", "title": "LDLR paper"}],
            warnings=["crossref-warning"],
            raw={"provider": "crossref"},
            meta={"total": 1},
        )

    monkeypatch.setattr(
        "src.domain.literature.gateway.adapters.crossref_adapter.call_crossref",
        fake_call_crossref,
    )

    adapter = CrossrefAdapter()
    result = await adapter.execute(
        ApiGatewayRequest(
            provider="crossref",
            action="search",
            query="ldlr",
            identifiers={"doi": "10.1000/xyz-123"},
            limit=7,
            raw=True,
            params={"mailto": "tests@example.org"},
        )
    )

    assert result.provider == "crossref"
    assert result.success is True
    assert result.items == [{"doi": "10.1000/xyz-123", "title": "LDLR paper"}]
    assert result.warnings == ["crossref-warning"]
    assert result.raw == {"provider": "crossref"}
    assert result.meta == {"total": 1}


@pytest.mark.asyncio
async def test_crossref_adapter_download_remains_unsupported() -> None:
    adapter = CrossrefAdapter()

    result = await adapter.execute(
        ApiGatewayRequest(
            provider="crossref",
            action="download",
            query="ldlr",
        )
    )

    assert result.provider == "crossref"
    assert result.success is False
    assert result.items == []
    assert result.downloads == []
    assert result.warnings == ["crossref_download_unsupported"]
