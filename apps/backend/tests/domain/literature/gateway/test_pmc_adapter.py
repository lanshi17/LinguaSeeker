import pytest

from src.domain.literature.gateway.api_gateway import (
    ApiGatewayRequest,
    ApiGatewayResult,
)
from src.domain.literature.gateway.adapters.pmc_adapter import PMCAdapter


@pytest.mark.asyncio
async def test_pmc_adapter_routes_pmid_search_through_existing_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_call_pmc_for_pmid(
        pmid,
        limit,
        raw,
        api_params,
    ):  # type: ignore[no-untyped-def]
        assert pmid == "12345678"
        assert limit == 3
        assert raw is True
        assert api_params == {"tool": "tests"}
        return ApiGatewayResult(
            provider="pmc",
            success=True,
            items=[{"pmcid": "PMC1234567", "title": "PMC article"}],
            warnings=["pmc-warning"],
            raw={"provider": "pmc"},
            meta={"total": 1},
        )

    monkeypatch.setattr(
        "src.domain.literature.gateway.adapters.pmc_adapter.call_pmc_for_pmid",
        fake_call_pmc_for_pmid,
    )

    adapter = PMCAdapter()
    result = await adapter.execute(
        ApiGatewayRequest(
            provider="pmc",
            action="search",
            identifiers={"pmid": "12345678"},
            limit=3,
            raw=True,
            params={"tool": "tests"},
        )
    )

    assert result.provider == "pmc"
    assert result.success is True
    assert result.items == [{"pmcid": "PMC1234567", "title": "PMC article"}]
    assert result.warnings == ["pmc-warning"]
    assert result.raw == {"provider": "pmc"}
    assert result.meta == {"total": 1}
