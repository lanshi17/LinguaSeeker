from __future__ import annotations

from typing import Any, Awaitable, Callable, Optional, override

from src.domain.literature.gateway.base import ProviderAdapter
from src.domain.literature.gateway.contracts import ApiGatewayRequest, ApiGatewayResult


OpenalexSearchCall = Callable[
    [str | None, str | None, int, bool, Optional[dict[str, Any]]],
    Awaitable[ApiGatewayResult],
]
OpenalexDownloadCall = Callable[
    [str | None, str | None, int, bool, str, int, Optional[dict[str, Any]]],
    Awaitable[ApiGatewayResult],
]


async def call_openalex(
    query: str | None,
    doi: str | None,
    limit: int,
    raw: bool,
    api_params: Optional[dict[str, Any]] = None,
) -> ApiGatewayResult:
    raise NotImplementedError("OpenAlex search helper is not configured")


async def call_openalex_download(
    query: str | None,
    doi: str | None,
    limit: int,
    raw: bool,
    download_path: str,
    selected_index: int,
    api_params: Optional[dict[str, Any]] = None,
) -> ApiGatewayResult:
    raise NotImplementedError("OpenAlex download helper is not configured")


class OpenAlexAdapter(ProviderAdapter):
    provider: str = "openalex"

    def __init__(
        self,
        search_call: OpenalexSearchCall | None = None,
        download_call: OpenalexDownloadCall | None = None,
    ) -> None:
        self._search_call = search_call or call_openalex
        self._download_call = download_call or call_openalex_download

    @override
    async def execute(self, request: ApiGatewayRequest) -> ApiGatewayResult:
        api_params = request.params or {}
        identifiers = request.identifiers or {}
        doi = identifiers.get("doi")

        if request.action == "download":
            return await self._download_call(
                request.query,
                doi,
                request.limit,
                request.raw,
                request.download_path,
                request.selected_index,
                api_params,
            )

        return await self._search_call(
            request.query,
            doi,
            request.limit,
            request.raw,
            api_params,
        )
