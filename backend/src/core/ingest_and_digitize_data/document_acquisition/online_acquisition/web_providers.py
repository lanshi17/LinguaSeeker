"""Web provider dispatcher — routes to pubscholar/cyberleninka/hans_publishers.

.. deprecated::
    This module is deprecated. Use ``web_search.firecrawl_adapter.FirecrawlAdapter`` instead.
"""

from __future__ import annotations

import warnings as _warnings
from typing import Any, Dict, Literal

from .contracts import OnlineAcquisitionGatewayResult, OnlineAcquisitionSourceTraceEntry

WebProvider = Literal["pubscholar", "cyberleninka", "hans_publishers", "chinaxiv", "koreascience", "redalyc", "la_referencia"]
ActionStrategy = Literal["search", "download"]


def _failure_result(provider: str, error: Exception, action: str = "search") -> OnlineAcquisitionGatewayResult:
    warnings = [f"{provider}_error:{error}"]
    return OnlineAcquisitionGatewayResult(
        provider=provider,
        success=False,
        items=[],
        downloads=[],
        warnings=warnings,
        source_trace=[
            OnlineAcquisitionSourceTraceEntry(
                provider=provider,
                attempt=1,
                action=action,
                success=False,
                items_count=0,
                downloads_count=0,
                warnings=warnings,
                error=str(error),
            )
        ],
    )


def _to_gateway_result(provider: str, action: str, result: Dict[str, Any]) -> OnlineAcquisitionGatewayResult:
    """Convert provider result dict to OnlineAcquisitionGatewayResult."""
    trace = OnlineAcquisitionSourceTraceEntry(
        provider=provider,
        attempt=1,
        action=action,
        success=bool(result.get("success")),
        items_count=len(result.get("items") or []),
        downloads_count=1 if result.get("file_path") else 0,
        warnings=list(result.get("warnings") or []),
    )

    downloads = []
    if result.get("file_path"):
        downloads.append({
            "file_path": result["file_path"],
            "pdf_url": result.get("pdf_url"),
        })

    return OnlineAcquisitionGatewayResult(
        provider=provider,
        success=bool(result.get("success")),
        items=list(result.get("items") or []),
        downloads=downloads,
        warnings=list(result.get("warnings") or []),
        raw=result,
        source_trace=[trace],
    )


async def call_web_provider(
    provider: str,
    action: str = "search",
    query: str = "",
    limit: int = 20,
    download_path: str = "./downloads",
    selected_index: int = 0,
    selected_title: str | None = None,
    detail_link: str | None = None,
    params: Dict[str, Any] | None = None,
) -> OnlineAcquisitionGatewayResult:
    """Unified entry point for web providers.

    .. deprecated::
        Use ``web_search.firecrawl_adapter.FirecrawlAdapter`` instead.
    """
    _warnings.warn(
        "call_web_provider is deprecated; use FirecrawlAdapter from web_search module",
        DeprecationWarning,
        stacklevel=2,
    )
    extra = params or {}

    if provider == "pubscholar":
        try:
            from .web.pubscholar import pubscholar_download, pubscholar_search
        except ImportError:
            return _failure_result("pubscholar", RuntimeError("pubscholar module not available"), action)
    elif provider == "cyberleninka":
        try:
            from .web.cyberleninka import cyberleninka_download, cyberleninka_search
        except ImportError:
            return _failure_result("cyberleninka", RuntimeError("cyberleninka module not available"), action)
    elif provider == "hans_publishers":
        try:
            from .web.hans_publishers import hanspub_download, hanspub_search
        except ImportError:
            return _failure_result("hans_publishers", RuntimeError("hans_publishers module not available"), action)
    elif provider == "chinaxiv":
        try:
            from .web.chinaxiv import chinaxiv_download, chinaxiv_search
        except ImportError:
            return _failure_result("chinaxiv", RuntimeError("chinaxiv module not available"), action)
    elif provider == "koreascience":
        try:
            from .web.koreascience import koreascience_download, koreascience_search
        except ImportError:
            return _failure_result("koreascience", RuntimeError("koreascience module not available"), action)
    elif provider == "redalyc":
        try:
            from .web.redalyc import redalyc_download, redalyc_search
        except ImportError:
            return _failure_result("redalyc", RuntimeError("redalyc module not available"), action)
    elif provider == "la_referencia":
        try:
            from .web.redalyc import la_referencia_download, la_referencia_search
        except ImportError:
            return _failure_result("la_referencia", RuntimeError("la_referencia module not available"), action)
    else:
        return _failure_result(provider, ValueError(f"unknown web provider: {provider}"), action)

    try:
        if action == "search":
            if provider == "pubscholar":
                result = await pubscholar_search(query=query, limit=limit, **extra)
            elif provider == "cyberleninka":
                result = await cyberleninka_search(query=query, limit=limit, **extra)
            elif provider == "chinaxiv":
                result = await chinaxiv_search(query=query, limit=limit, **extra)
            elif provider == "koreascience":
                result = await koreascience_search(query=query, limit=limit, **extra)
            elif provider == "redalyc":
                result = await redalyc_search(query=query, limit=limit, **extra)
            elif provider == "la_referencia":
                result = await la_referencia_search(query=query, limit=limit, **extra)
            else:
                result = await hanspub_search(query=query, limit=limit, **extra)
        else:
            if provider == "pubscholar":
                result = await pubscholar_download(
                    query=query, detail_link=detail_link,
                    selected_index=selected_index, selected_title=selected_title,
                    download_path=download_path, **extra,
                )
            elif provider == "cyberleninka":
                result = await cyberleninka_download(
                    query=query, detail_link=detail_link,
                    selected_index=selected_index, selected_title=selected_title,
                    download_path=download_path, **extra,
                )
            elif provider == "chinaxiv":
                result = await chinaxiv_download(
                    query=query, detail_link=detail_link,
                    selected_index=selected_index, selected_title=selected_title,
                    download_path=download_path, **extra,
                )
            elif provider == "koreascience":
                result = await koreascience_download(
                    query=query, detail_link=detail_link,
                    selected_index=selected_index, selected_title=selected_title,
                    download_path=download_path, **extra,
                )
            elif provider == "redalyc":
                result = await redalyc_download(
                    query=query, detail_link=detail_link,
                    selected_index=selected_index, selected_title=selected_title,
                    download_path=download_path, **extra,
                )
            elif provider == "la_referencia":
                result = await la_referencia_download(
                    query=query, detail_link=detail_link,
                    selected_index=selected_index, selected_title=selected_title,
                    download_path=download_path, **extra,
                )
            else:
                result = await hanspub_download(
                    query=query, detail_link=detail_link,
                    selected_index=selected_index, selected_title=selected_title,
                    download_path=download_path, **extra,
                )

        return _to_gateway_result(provider, action, result)
    except Exception as exc:
        return _failure_result(provider, exc, action)
