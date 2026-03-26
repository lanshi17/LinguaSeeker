from __future__ import annotations

from typing import Any, Awaitable, Callable, Optional, override

from src.domain.literature.gateway.base import ProviderAdapter
from src.domain.literature.gateway.contracts import ApiGatewayRequest, ApiGatewayResult

PmcMetadataCall = Callable[
    [list[str], bool, Optional[dict[str, Any]]], Awaitable[ApiGatewayResult]
]
PmcSearchCall = Callable[
    [str, int, bool, Optional[dict[str, Any]]], Awaitable[ApiGatewayResult]
]
PmcForPmidCall = Callable[
    [str, int, bool, Optional[dict[str, Any]]], Awaitable[ApiGatewayResult]
]


async def call_pmc_metadata(
    pmcids: list[str],
    raw: bool,
    api_params: Optional[dict[str, Any]] = None,
) -> ApiGatewayResult:
    raise NotImplementedError("PMC metadata helper is not configured")


async def call_pmc_search(
    term: str,
    limit: int,
    raw: bool,
    api_params: Optional[dict[str, Any]] = None,
) -> ApiGatewayResult:
    raise NotImplementedError("PMC search helper is not configured")


async def call_pmc_for_pmid(
    pmid: str,
    limit: int,
    raw: bool,
    api_params: Optional[dict[str, Any]] = None,
) -> ApiGatewayResult:
    raise NotImplementedError("PMC PMID helper is not configured")


class PMCAdapter(ProviderAdapter):
    provider: str = "pmc"

    def __init__(
        self,
        metadata_call: PmcMetadataCall | None = None,
        search_call: PmcSearchCall | None = None,
        pmid_call: PmcForPmidCall | None = None,
    ) -> None:
        self._metadata_call = metadata_call or call_pmc_metadata
        self._search_call = search_call or call_pmc_search
        self._pmid_call = pmid_call or call_pmc_for_pmid

    @override
    async def execute(self, request: ApiGatewayRequest) -> ApiGatewayResult:
        identifiers = request.identifiers or {}
        api_params = request.params or {}
        pmcid = identifiers.get("pmcid")
        pmid = identifiers.get("pmid")

        if pmcid:
            return await self._metadata_call([pmcid], request.raw, api_params)

        if pmid:
            return await self._pmid_call(
                pmid,
                request.limit,
                request.raw,
                api_params,
            )

        search_result = await self._search_call(
            request.query or "",
            request.limit,
            request.raw,
            api_params,
        )
        pmcids = [
            found_pmcid
            for item in search_result.items
            if isinstance((found_pmcid := item.get("pmcid")), str)
        ]
        if not pmcids:
            return search_result

        metadata_result = await self._metadata_call(
            pmcids[: request.limit],
            request.raw,
            api_params,
        )
        metadata_result.warnings = search_result.warnings + metadata_result.warnings
        return metadata_result
