from __future__ import annotations

from typing import Any, Awaitable, Callable, Optional, override

from src.domain.literature.gateway.base import ProviderAdapter
from src.domain.literature.gateway.contracts import ApiGatewayRequest, ApiGatewayResult


EuropepmcSearchCall = Callable[
    [str | None, str | None, int, bool, Optional[dict[str, Any]]],
    Awaitable[ApiGatewayResult],
]
EuropepmcDownloadCall = Callable[
    [str | None, str | None, int, bool, str, int, Optional[dict[str, Any]]],
    Awaitable[ApiGatewayResult],
]


async def call_europepmc(
    query: str | None,
    doi: str | None,
    limit: int,
    raw: bool,
    api_params: Optional[dict[str, Any]] = None,
) -> ApiGatewayResult:
    raise NotImplementedError("Europe PMC search helper is not configured")


async def call_europepmc_download(
    query: str | None,
    doi: str | None,
    limit: int,
    raw: bool,
    download_path: str,
    selected_index: int,
    api_params: Optional[dict[str, Any]] = None,
) -> ApiGatewayResult:
    raise NotImplementedError("Europe PMC download helper is not configured")


class EuropePmcAdapter(ProviderAdapter):
    provider: str = "europepmc"

    def __init__(
        self,
        search_call: EuropepmcSearchCall | None = None,
        download_call: EuropepmcDownloadCall | None = None,
    ) -> None:
        self._search_call = search_call or call_europepmc
        self._download_call = download_call or call_europepmc_download

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
