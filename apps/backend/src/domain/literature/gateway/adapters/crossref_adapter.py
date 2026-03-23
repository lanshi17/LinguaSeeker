from typing import Any, Awaitable, Callable, Dict, Optional

from src.domain.literature.gateway.base import LiteratureGatewayAdapter

CrossrefSearchCallable = Callable[
    [Optional[str], int, bool, Optional[str], Optional[Dict[str, Any]]],
    Awaitable[Any],
]
CrossrefUnsupportedDownloadFactory = Callable[[], Any]


class CrossrefGatewayAdapter(LiteratureGatewayAdapter):
    provider: str = "crossref"

    def __init__(
        self,
        search_fn: CrossrefSearchCallable,
        unsupported_download_factory: CrossrefUnsupportedDownloadFactory,
    ) -> None:
        self._search_fn = search_fn
        self._unsupported_download_factory = unsupported_download_factory

    async def execute(self, request: Any) -> Any:
        identifiers = request.identifiers or {}
        api_params = request.params or {}

        if request.action == "download":
            return self._unsupported_download_factory()

        return await self._search_fn(
            request.query,
            request.limit,
            request.raw,
            _crossref_filter_from_identifiers(identifiers),
            api_params,
        )


def _crossref_filter_from_identifiers(
    identifiers: Dict[str, Optional[str]],
) -> Optional[str]:
    doi = identifiers.get("doi")
    issn = identifiers.get("issn")
    if doi:
        return f"doi:{doi}"
    if issn:
        return f"issn:{issn}"
    return None
