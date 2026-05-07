"""Web provider dispatcher — routes to pubscholar/cyberleninka/hans_publishers."""

from __future__ import annotations

from typing import Any, Dict, Literal

from .contracts import GatewayResult, SourceTraceEntry

WebProvider = Literal["pubscholar", "cyberleninka", "hans_publishers"]
ActionStrategy = Literal["search", "download"]


def _failure_result(provider: str, error: Exception, action: str = "search") -> GatewayResult:
    warnings = [f"{provider}_error:{error}"]
    return GatewayResult(
        provider=provider,
        success=False,
        items=[],
        downloads=[],
        warnings=warnings,
        source_trace=[
            SourceTraceEntry(
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


def _to_gateway_result(provider: str, action: str, result: Dict[str, Any]) -> GatewayResult:
    """Convert provider result dict to GatewayResult."""
    trace = SourceTraceEntry(
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

    return GatewayResult(
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
) -> GatewayResult:
    """Unified entry point for web providers."""
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
    else:
        return _failure_result(provider, ValueError(f"unknown web provider: {provider}"), action)

    try:
        if action == "search":
            if provider == "pubscholar":
                result = await pubscholar_search(query=query, limit=limit, **extra)
            elif provider == "cyberleninka":
                result = await cyberleninka_search(query=query, limit=limit, **extra)
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
            else:
                result = await hanspub_download(
                    query=query, detail_link=detail_link,
                    selected_index=selected_index, selected_title=selected_title,
                    download_path=download_path, **extra,
                )

        return _to_gateway_result(provider, action, result)
    except Exception as exc:
        return _failure_result(provider, exc, action)
