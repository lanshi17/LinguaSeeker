"""Web provider (pubscholar/cyberleninka/hans_publishers) via crawl4ai.

These providers use JavaScript-rendered web scraping. They depend on crawl4ai
(Playwright-based) for full browser automation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

from .contracts import GatewayResult, SourceTraceEntry

WebProvider = Literal["pubscholar", "cyberleninka", "hans_publishers"]
ActionStrategy = Literal["search", "download"]


@dataclass
class WebGatewayRequest:
    """Request for web provider call."""

    provider: WebProvider
    action: ActionStrategy = "search"
    query: Optional[str] = None
    limit: int = 20
    params: Dict[str, Any] = field(default_factory=dict)
    download_path: str = "./downloads"
    selected_index: int = 0
    selected_title: Optional[str] = None
    detail_link: Optional[str] = None


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


async def call_pubscholar(request: WebGatewayRequest) -> GatewayResult:
    """Call PubScholar web provider."""
    try:
        from src.domain.literature.automated_web.pubscholar.pubscholar import (
            pubscholar_workflow,
        )
    except ImportError:
        return _failure_result(
            "pubscholar",
            RuntimeError("pubscholar module not available"),
        )

    payload: Dict[str, Any] = {
        "action": request.action,
        "search_params": {
            "keyword": request.query or "",
            "filters": {},
            "limit": request.limit,
        },
    }
    if request.action == "download":
        payload["selected_index"] = request.selected_index
        payload["download_path"] = request.download_path
        if request.selected_title:
            payload["selected_title"] = request.selected_title
        if request.detail_link:
            payload["detail_link"] = request.detail_link
    if request.params:
        payload.update(request.params)

    try:
        response = await pubscholar_workflow(payload)
        trace = SourceTraceEntry(
            provider="pubscholar",
            attempt=1,
            action=request.action,
            success=bool(response.get("success")),
            items_count=len(response.get("items") or []),
            downloads_count=len(response.get("downloads") or []),
            warnings=list(response.get("warnings") or []),
        )
        return GatewayResult(
            provider="pubscholar",
            success=bool(response.get("success")),
            items=list(response.get("items") or []),
            downloads=list(response.get("downloads") or []),
            warnings=list(response.get("warnings") or []),
            raw=response,
            source_trace=[trace],
        )
    except Exception as exc:
        return _failure_result("pubscholar", exc)


async def call_cyberleninka(request: WebGatewayRequest) -> GatewayResult:
    """Call CyberLeninka web provider."""
    try:
        from src.domain.literature.automated_web.cyberleninka.cyberleninka import (
            cyberleninka_workflow,
        )
    except ImportError:
        return _failure_result(
            "cyberleninka",
            RuntimeError("cyberleninka module not available"),
        )

    payload: Dict[str, Any] = {
        "action": request.action,
        "search_params": {
            "keyword": request.query or "",
            "filters": {},
            "limit": request.limit,
        },
    }
    if request.action == "download":
        payload["selected_index"] = request.selected_index
        payload["download_path"] = request.download_path
        if request.selected_title:
            payload["selected_title"] = request.selected_title
        if request.detail_link:
            payload["detail_link"] = request.detail_link
    if request.params:
        payload.update(request.params)

    try:
        response = await cyberleninka_workflow(payload)
        trace = SourceTraceEntry(
            provider="cyberleninka",
            attempt=1,
            action=request.action,
            success=bool(response.get("success")),
            items_count=len(response.get("items") or []),
            downloads_count=len(response.get("downloads") or []),
            warnings=list(response.get("warnings") or []),
        )
        return GatewayResult(
            provider="cyberleninka",
            success=bool(response.get("success")),
            items=list(response.get("items") or []),
            downloads=list(response.get("downloads") or []),
            warnings=list(response.get("warnings") or []),
            raw=response,
            source_trace=[trace],
        )
    except Exception as exc:
        return _failure_result("cyberleninka", exc)


async def call_hans_publishers(request: WebGatewayRequest) -> GatewayResult:
    """Call Hans Publishers web provider."""
    try:
        from src.domain.literature.automated_web.hans_publishers.hans_publishers import (
            hanspub_workflow,
        )
    except ImportError:
        return _failure_result(
            "hans_publishers",
            RuntimeError("hans_publishers module not available"),
        )

    payload: Dict[str, Any] = {
        "action": request.action,
        "search_params": {
            "keyword": request.query or "",
            "filters": {},
            "limit": request.limit,
        },
    }
    if request.action == "download":
        payload["selected_index"] = request.selected_index
        payload["download_path"] = request.download_path
        if request.selected_title:
            payload["selected_title"] = request.selected_title
        if request.detail_link:
            payload["detail_link"] = request.detail_link
    if request.params:
        payload.update(request.params)

    try:
        response = await hanspub_workflow(payload)
        trace = SourceTraceEntry(
            provider="hans_publishers",
            attempt=1,
            action=request.action,
            success=bool(response.get("success")),
            items_count=len(response.get("items") or []),
            downloads_count=len(response.get("downloads") or []),
            warnings=list(response.get("warnings") or []),
        )
        return GatewayResult(
            provider="hans_publishers",
            success=bool(response.get("success")),
            items=list(response.get("items") or []),
            downloads=list(response.get("downloads") or []),
            warnings=list(response.get("warnings") or []),
            raw=response,
            source_trace=[trace],
        )
    except Exception as exc:
        return _failure_result("hans_publishers", exc)


async def call_web_provider(request: WebGatewayRequest) -> GatewayResult:
    """Unified entry point for web providers."""
    dispatch = {
        "pubscholar": call_pubscholar,
        "cyberleninka": call_cyberleninka,
        "hans_publishers": call_hans_publishers,
    }
    handler = dispatch.get(request.provider)
    if not handler:
        return _failure_result(
            request.provider,
            ValueError(f"unknown web provider: {request.provider}"),
        )
    return await handler(request)
