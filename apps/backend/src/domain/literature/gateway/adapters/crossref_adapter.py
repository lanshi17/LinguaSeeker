from __future__ import annotations

from typing import Any, Awaitable, Callable, Optional, override

from src.domain.literature.gateway.base import ProviderAdapter
from src.domain.literature.gateway.contracts import ApiGatewayRequest, ApiGatewayResult

CrossrefSearchCall = Callable[
    [str | None, int, bool, str | None, Optional[dict[str, Any]]],
    Awaitable[ApiGatewayResult],
]


async def call_crossref(
    query: str | None,
    limit: int,
    raw: bool,
    filter_expr: str | None = None,
    api_params: Optional[dict[str, Any]] = None,
) -> ApiGatewayResult:
    raise NotImplementedError("Crossref search helper is not configured")


class CrossrefAdapter(ProviderAdapter):
    provider: str = "crossref"

    def __init__(self, search_call: CrossrefSearchCall | None = None) -> None:
        self._search_call = search_call or call_crossref

    @override
    async def execute(self, request: ApiGatewayRequest) -> ApiGatewayResult:
        if request.action == "download":
            return ApiGatewayResult(
                provider="crossref",
                success=False,
                items=[],
                warnings=["crossref_download_unsupported"],
                downloads=[],
            )

        identifiers = request.identifiers or {}
        filter_expr = None
        if doi := identifiers.get("doi"):
            filter_expr = f"doi:{doi}"
        return await self._search_call(
            request.query,
            request.limit,
            request.raw,
            filter_expr,
            request.params or {},
        )
