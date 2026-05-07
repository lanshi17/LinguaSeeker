"""Web provider dispatcher — routes to pubscholar/cyberleninka/hans_publishers."""

from __future__ import annotations

from typing import Any, Dict, List, Literal

from .contracts import GatewayResult, SourceTraceEntry

WebProvider = Literal["pubscholar", "cyberleninka", "hans_publishers"]
ActionStrategy = Literal["search", "download"]


def _failure_result(provider: str, error: Exception) -> GatewayResult:
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
                action="search",
                success=False,
                items_count=0,
                downloads_count=0,
                warnings=warnings,
                error=str(error),
            )
        ],
    )


async def call_pubscholar(
    action: str,
    query: str,
    limit: int = 20,
    download_path: str = "./downloads",
    selected_index: int = 0,
    selected_title: str | None = None,
    detail_link: str | None = None,
    params: Dict[str, Any] | None = None,
) -> GatewayResult:
    """Call PubScholar web provider."""
    try:
        from .web.pubscholar import pubscholar_download, pubscholar_search
    except ImportError:
        return _failure_result("pubscholar", RuntimeError("pubscholar module not available"))

    try:
        if action == "search":
            result = await pubscholar_search(
                query=query,
                limit=limit,
                **(params or {}),
            )
        else:
            result = await pubscholar_download(
                query=query,
                detail_link=detail_link,
                selected_index=selected_index,
                selected_title=selected_title,
                download_path=download_path,
                **(params or {}),
            )

        trace = SourceTraceEntry(
            provider="pubscholar",
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
            provider="pubscholar",
            success=bool(result.get("success")),
            items=list(result.get("items") or []),
            downloads=downloads,
            warnings=list(result.get("warnings") or []),
            raw=result,
            source_trace=[trace],
        )
    except Exception as exc:
        return _failure_result("pubscholar", exc)


async def call_cyberleninka(
    action: str,
    query: str,
    limit: int = 20,
    download_path: str = "./downloads",
    selected_index: int = 0,
    selected_title: str | None = None,
    detail_link: str | None = None,
    params: Dict[str, Any] | None = None,
) -> GatewayResult:
    """Call CyberLeninka web provider."""
    try:
        from .web.cyberleninka import cyberleninka_download, cyberleninka_search
    except ImportError:
        return _failure_result("cyberleninka", RuntimeError("cyberleninka module not available"))

    try:
        if action == "search":
            result = await cyberleninka_search(
                query=query,
                limit=limit,
                **(params or {}),
            )
        else:
            result = await cyberleninka_download(
                query=query,
                detail_link=detail_link,
                selected_index=selected_index,
                selected_title=selected_title,
                download_path=download_path,
                **(params or {}),
            )

        trace = SourceTraceEntry(
            provider="cyberleninka",
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
            provider="cyberleninka",
            success=bool(result.get("success")),
            items=list(result.get("items") or []),
            downloads=downloads,
            warnings=list(result.get("warnings") or []),
            raw=result,
            source_trace=[trace],
        )
    except Exception as exc:
        return _failure_result("cyberleninka", exc)


async def call_hans_publishers(
    action: str,
    query: str,
    limit: int = 20,
    download_path: str = "./downloads",
    selected_index: int = 0,
    selected_title: str | None = None,
    detail_link: str | None = None,
    params: Dict[str, Any] | None = None,
) -> GatewayResult:
    """Call Hans Publishers web provider."""
    try:
        from .web.hans_publishers import hanspub_download, hanspub_search
    except ImportError:
        return _failure_result("hans_publishers", RuntimeError("hans_publishers module not available"))

    try:
        if action == "search":
            result = await hanspub_search(
                query=query,
                limit=limit,
                **(params or {}),
            )
        else:
            result = await hanspub_download(
                query=query,
                detail_link=detail_link,
                selected_index=selected_index,
                selected_title=selected_title,
                download_path=download_path,
                **(params or {}),
            )

        trace = SourceTraceEntry(
            provider="hans_publishers",
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
            provider="hans_publishers",
            success=bool(result.get("success")),
            items=list(result.get("items") or []),
            downloads=downloads,
            warnings=list(result.get("warnings") or []),
            raw=result,
            source_trace=[trace],
        )
    except Exception as exc:
        return _failure_result("hans_publishers", exc)


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
    dispatch = {
        "pubscholar": call_pubscholar,
        "cyberleninka": call_cyberleninka,
        "hans_publishers": call_hans_publishers,
    }
    handler = dispatch.get(provider)
    if not handler:
        return _failure_result(
            provider,
            ValueError(f"unknown web provider: {provider}"),
        )
    return await handler(
        action=action,
        query=query,
        limit=limit,
        download_path=download_path,
        selected_index=selected_index,
        selected_title=selected_title,
        detail_link=detail_link,
        params=params,
    )
