from __future__ import annotations

from typing import Any, Awaitable, Callable, Optional, override

from src.domain.literature.gateway.base import ProviderAdapter
from src.domain.literature.gateway.contracts import ApiGatewayRequest, ApiGatewayResult

UnpaywallSearchCall = Callable[
    [str | None, str | None, int, bool, Optional[dict[str, Any]]],
    Awaitable[ApiGatewayResult],
]
UnpaywallDownloadCall = Callable[
    [str | None, str | None, int, bool, str, int, Optional[dict[str, Any]]],
    Awaitable[ApiGatewayResult],
]


async def call_unpaywall(
    query: str | None,
    doi: str | None,
    limit: int,
    raw: bool,
    api_params: Optional[dict[str, Any]] = None,
) -> ApiGatewayResult:
    raise NotImplementedError("Unpaywall search helper is not configured")


async def call_unpaywall_download(
    query: str | None,
    doi: str | None,
    limit: int,
    raw: bool,
    download_path: str,
    selected_index: int,
    api_params: Optional[dict[str, Any]] = None,
) -> ApiGatewayResult:
    raise NotImplementedError("Unpaywall download helper is not configured")


class UnpaywallAdapter(ProviderAdapter):
    provider: str = "unpaywall"

    def __init__(
        self,
        search_call: UnpaywallSearchCall | None = None,
        download_call: UnpaywallDownloadCall | None = None,
    ) -> None:
        self._search_call = search_call or call_unpaywall
        self._download_call = download_call or call_unpaywall_download

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
