from dataclasses import dataclass
from typing import Any

import pytest

from src.domain.literature.gateway.adapters.crossref_adapter import (
    CrossrefGatewayAdapter,
)
from src.domain.literature.gateway.api_gateway import (
    ApiGatewayRequest,
    ApiGatewayResult,
)


@dataclass
class _RecordedCall:
    args: tuple[Any, ...]
    kwargs: dict[str, Any]


async def _unexpected_search(*args: Any, **kwargs: Any) -> ApiGatewayResult:
    raise AssertionError(f"search should not be called: args={args}, kwargs={kwargs}")


def _unsupported_download_result() -> ApiGatewayResult:
    return ApiGatewayResult(
        provider="crossref",
        success=False,
        items=[],
        downloads=[],
        warnings=["crossref_download_unsupported"],
    )


@pytest.mark.asyncio
async def test_crossref_adapter_delegates_search_with_doi_filter() -> None:
    recorded: _RecordedCall | None = None

    async def fake_search(
        query: str | None,
        limit: int,
        raw: bool,
        filter_expr: str | None,
        api_params: dict[str, Any] | None,
    ) -> ApiGatewayResult:
        nonlocal recorded
        recorded = _RecordedCall((query, limit, raw, filter_expr, api_params), {})
        return ApiGatewayResult(
            provider="crossref",
            success=True,
            items=[{"doi": "10.1000/xyz-123", "title": "Crossref result"}],
            warnings=[],
        )

    adapter = CrossrefGatewayAdapter(
        search_fn=fake_search,
        unsupported_download_factory=_unsupported_download_result,
    )

    result = await adapter.execute(
        ApiGatewayRequest(
            provider="crossref",
            action="search",
            query="familial hypercholesterolemia",
            identifiers={"doi": "10.1000/xyz-123", "issn": "1234-5678"},
            limit=9,
            raw=True,
            params={"source": "crossref-freeze"},
        )
    )

    assert recorded is not None
    assert recorded.args == (
        "familial hypercholesterolemia",
        9,
        True,
        "doi:10.1000/xyz-123",
        {"source": "crossref-freeze"},
    )
    assert result.provider == "crossref"
    assert result.success is True
    assert result.items == [{"doi": "10.1000/xyz-123", "title": "Crossref result"}]
    assert result.warnings == []


@pytest.mark.asyncio
async def test_crossref_adapter_falls_back_to_issn_filter_when_doi_missing() -> None:
    recorded: _RecordedCall | None = None

    async def fake_search(
        query: str | None,
        limit: int,
        raw: bool,
        filter_expr: str | None,
        api_params: dict[str, Any] | None,
    ) -> ApiGatewayResult:
        nonlocal recorded
        recorded = _RecordedCall((query, limit, raw, filter_expr, api_params), {})
        return ApiGatewayResult(
            provider="crossref",
            success=True,
            items=[{"issn": "1234-5678", "title": "ISSN fallback"}],
            warnings=[],
        )

    adapter = CrossrefGatewayAdapter(
        search_fn=fake_search,
        unsupported_download_factory=_unsupported_download_result,
    )

    result = await adapter.execute(
        ApiGatewayRequest(
            provider="crossref",
            action="search",
            query="ldlr",
            identifiers={"issn": "1234-5678"},
            limit=5,
            raw=False,
            params={"source": "issn-freeze"},
        )
    )

    assert recorded is not None
    assert recorded.args == (
        "ldlr",
        5,
        False,
        "issn:1234-5678",
        {"source": "issn-freeze"},
    )
    assert result.provider == "crossref"
    assert result.success is True
    assert result.items == [{"issn": "1234-5678", "title": "ISSN fallback"}]


@pytest.mark.asyncio
async def test_crossref_adapter_marks_download_as_unsupported() -> None:
    adapter = CrossrefGatewayAdapter(
        search_fn=_unexpected_search,
        unsupported_download_factory=_unsupported_download_result,
    )

    result = await adapter.execute(
        ApiGatewayRequest(provider="crossref", action="download", query="ldlr")
    )

    assert result.provider == "crossref"
    assert result.success is False
    assert result.items == []
    assert result.downloads == []
    assert result.warnings == ["crossref_download_unsupported"]
