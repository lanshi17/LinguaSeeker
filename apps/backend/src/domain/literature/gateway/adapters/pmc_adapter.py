from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, List, Optional

from src.domain.literature.gateway.base import LiteratureGatewayAdapter

PmcDownloadCallable = Callable[
    [
        Optional[str],
        Dict[str, Optional[str]],
        int,
        bool,
        str,
        Optional[Dict[str, Any]],
    ],
    Awaitable[Any],
]
PmcForPmidCallable = Callable[
    [str, int, bool, Optional[Dict[str, Any]]],
    Awaitable[Any],
]
PmcMetadataCallable = Callable[
    [List[str], bool, Optional[Dict[str, Any]]],
    Awaitable[Any],
]
PmcSearchCallable = Callable[
    [str, int, bool, Optional[Dict[str, Any]]],
    Awaitable[Any],
]


class PmcGatewayAdapter(LiteratureGatewayAdapter):
    provider: str = "pmc"

    def __init__(
        self,
        *,
        metadata_fn: PmcMetadataCallable,
        pmid_fn: PmcForPmidCallable,
        search_fn: PmcSearchCallable,
        download_fn: PmcDownloadCallable,
    ) -> None:
        self._metadata_fn = metadata_fn
        self._pmid_fn = pmid_fn
        self._search_fn = search_fn
        self._download_fn = download_fn

    async def execute(self, request: Any) -> Any:
        identifiers = request.identifiers or {}
        api_params = request.params or {}

        if request.action == "download":
            return await self._download_fn(
                request.query,
                identifiers,
                request.limit,
                request.raw,
                request.download_path,
                api_params,
            )

        pmcid = identifiers.get("pmcid")
        pmid = identifiers.get("pmid")

        if pmcid:
            return await self._metadata_fn(
                [pmcid],
                request.raw,
                api_params,
            )

        if pmid:
            return await self._pmid_fn(
                pmid,
                request.limit,
                request.raw,
                api_params,
            )

        search_result = await self._search_fn(
            request.query or "",
            request.limit,
            request.raw,
            api_params,
        )
        pmcids: List[str] = []
        for item in search_result.items:
            pmcid_value = item.get("pmcid")
            if pmcid_value is not None:
                pmcids.append(str(pmcid_value))
        if not pmcids:
            return search_result

        metadata_result = await self._metadata_fn(
            pmcids[: request.limit],
            request.raw,
            api_params,
        )
        metadata_result.warnings = search_result.warnings + metadata_result.warnings
        return metadata_result
