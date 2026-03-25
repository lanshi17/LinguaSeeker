from __future__ import annotations

from typing import Any, Awaitable, Callable, Optional, override

from src.domain.literature.gateway.base import ProviderAdapter
from src.domain.literature.gateway.contracts import ApiGatewayRequest, ApiGatewayResult

JStageSearchCall = Callable[
    [str | None, int, bool, Optional[dict[str, Any]]], Awaitable[ApiGatewayResult]
]
JStageDownloadCall = Callable[
    [
        str | None,
        int,
        bool,
        str,
        int,
        str | None,
        str | None,
        Optional[dict[str, Any]],
    ],
    Awaitable[ApiGatewayResult],
]


async def call_jstage(
    query: str | None,
    limit: int,
    raw: bool,
    api_params: Optional[dict[str, Any]] = None,
) -> ApiGatewayResult:
    raise NotImplementedError("JStage search helper is not configured")


async def call_jstage_download(
    query: str | None,
    limit: int,
    raw: bool,
    download_path: str,
    selected_index: int,
    selected_title: str | None,
    detail_link: str | None,
    api_params: Optional[dict[str, Any]] = None,
) -> ApiGatewayResult:
    raise NotImplementedError("JStage download helper is not configured")


class JStageAdapter(ProviderAdapter):
    provider: str = "jstage"

    def __init__(
        self,
        search_call: JStageSearchCall | None = None,
        download_call: JStageDownloadCall | None = None,
    ) -> None:
        self._search_call = search_call or call_jstage
        self._download_call = download_call or call_jstage_download

    @override
    async def execute(self, request: ApiGatewayRequest) -> ApiGatewayResult:
        api_params = request.params or {}
        if request.action == "download":
            return await self._download_call(
                request.query,
                request.limit,
                request.raw,
                request.download_path,
                request.selected_index,
                request.selected_title,
                request.detail_link,
                api_params,
            )

        return await self._search_call(
            request.query,
            request.limit,
            request.raw,
            api_params,
        )
