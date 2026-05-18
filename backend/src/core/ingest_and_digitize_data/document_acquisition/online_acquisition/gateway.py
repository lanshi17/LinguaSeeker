"""Unified gateway — delegates HTTP I/O to net_io, Python handles downloads."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

import httpx

from .contracts import OnlineAcquisitionGatewayRequest, OnlineAcquisitionGatewayResult, OnlineAcquisitionSourceTraceEntry

_PDF_LINK_PATTERNS = [
    re.compile(r'href=["\']([^"\']*\.pdf[^"\']*)["\']', re.IGNORECASE),
    re.compile(r'href=["\']([^"\']*download[^"\']*pdf[^"\']*)["\']', re.IGNORECASE),
]

# Unicode hyphen/dash variants that should be normalized to ASCII hyphen in DOIs
_HYPHEN_CHARS = "‐‑‒–—―⁃−﹘﹣－"
_HYPHEN_TABLE = str.maketrans(_HYPHEN_CHARS, "-" * len(_HYPHEN_CHARS))


def _normalize_doi(doi: str) -> str:
    """Normalize unicode hyphen/dash variants to ASCII hyphen in DOIs."""
    return doi.translate(_HYPHEN_TABLE)


def _sanitize_filename(name: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|]+", "_", str(name or "").strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return (cleaned or "paper")[:120]


def _extract_pdf_links_from_html(html: str, base_url: str) -> List[str]:
    links: List[str] = []
    for pattern in _PDF_LINK_PATTERNS:
        for match in pattern.finditer(html):
            href = match.group(1)
            absolute = urljoin(base_url, href)
            if absolute not in links:
                links.append(absolute)
    return links


def _choose_item(
    items: List[Dict[str, Any]],
    selected_index: int,
    selected_title: Optional[str],
    title_keys: List[str],
) -> Optional[Dict[str, Any]]:
    """Select an item by title match or index."""

    def _read_key(item: Dict[str, Any], key: str) -> str:
        if "." not in key:
            return str(item.get(key) or "").strip()
        current: Any = item
        for part in key.split("."):
            if not isinstance(current, dict):
                return ""
            current = current.get(part)
        return str(current or "").strip()

    if selected_title:
        wanted = str(selected_title).strip().lower()
        for item in items:
            for key in title_keys:
                title = _read_key(item, key).lower()
                if title and wanted in title:
                    return item
    if 0 <= selected_index < len(items):
        return items[selected_index]
    return None


async def _download_pdf_from_candidates(
    candidates: List[str],
    download_path: str,
    filename_stem: str,
    proxy: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str], List[str]]:
    """Try downloading PDF from candidate URLs. Returns (file_path, pdf_url, warnings)."""
    warnings: List[str] = []
    queue = [str(url).strip() for url in candidates if str(url).strip()]
    visited: set[str] = set()
    target = Path(download_path) / f"{_sanitize_filename(filename_stem)}.pdf"
    target.parent.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient(
        timeout=60,
        follow_redirects=True,
        proxy=proxy,
    ) as client:
        while queue:
            url = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)
            try:
                response = await client.get(url)
                response.raise_for_status()
            except Exception as exc:
                warnings.append(f"download_failed:{url}:{exc}")
                continue

            content = response.content or b""
            content_type = str(response.headers.get("content-type") or "").lower()
            final_url = str(response.url)

            if content.startswith(b"%PDF"):
                target.write_bytes(content)
                return str(target), final_url, warnings

            if "html" in content_type or b"<html" in content[:2048].lower():
                extra = _extract_pdf_links_from_html(response.text or "", final_url or url)
                for link in extra:
                    if link not in visited:
                        queue.append(link)
                continue

            warnings.append(f"non_pdf_content_type:{content_type or 'unknown'}")

    return None, None, warnings


def _build_fetch_params(request: OnlineAcquisitionGatewayRequest) -> Dict[str, Any]:
    """Convert OnlineAcquisitionGatewayRequest to net_io.fetch_one params dict."""
    params: Dict[str, Any] = {
        "query": request.query or "",
        "limit": request.limit,
        "raw": request.raw,
        "selected_index": request.selected_index,
    }
    if request.selected_title is not None:
        params["selected_title"] = request.selected_title
    if request.detail_link is not None:
        params["detail_link"] = request.detail_link
    if request.identifiers:
        identifiers = {}
        for k, v in request.identifiers.items():
            if v is None:
                continue
            if k == "doi":
                v = _normalize_doi(v)
            identifiers[k] = v
        params["identifiers"] = identifiers
    return {k: v for k, v in params.items() if v is not None}


def _rust_result_to_gateway(
    provider: str,
    result: Dict[str, Any],
    trace: Optional[OnlineAcquisitionSourceTraceEntry] = None,
) -> OnlineAcquisitionGatewayResult:
    """Convert net_io FetchResult dict to OnlineAcquisitionGatewayResult."""
    gateway_result = OnlineAcquisitionGatewayResult(
        provider=provider,
        success=bool(result.get("success")),
        items=list(result.get("items") or []),
        downloads=list(result.get("downloads") or []),
        warnings=list(result.get("warnings") or []),
        raw=result.get("raw"),
        meta=result.get("meta"),
    )
    if trace:
        gateway_result.source_trace = [trace]
    return gateway_result


def _failure_result(provider: str, error: Exception, action: str = "search") -> OnlineAcquisitionGatewayResult:
    warnings = [f"{provider}_error:{error}"]
    trace = OnlineAcquisitionSourceTraceEntry(
        provider=provider,
        attempt=1,
        action=action,
        success=False,
        items_count=0,
        downloads_count=0,
        warnings=warnings,
        error=str(error),
    )
    return OnlineAcquisitionGatewayResult(
        provider=provider,
        success=False,
        items=[],
        downloads=[],
        warnings=warnings,
        source_trace=[trace],
    )


async def call_provider(request: OnlineAcquisitionGatewayRequest) -> OnlineAcquisitionGatewayResult:
    """Call a single provider via net_io.fetch_one."""
    import time as _time
    from .provider_health import get_health_tracker

    start = _time.monotonic()
    try:
        import rust_io.net as net_io
    except ImportError:
        elapsed = (_time.monotonic() - start) * 1000
        get_health_tracker().record(request.provider, success=False, latency_ms=elapsed)
        return _failure_result(
            request.provider,
            RuntimeError("net_io not available"),
            request.action,
        )

    params = _build_fetch_params(request)
    try:
        raw_result = await net_io.fetch_one(
            provider=request.provider,
            action=request.action,
            params=params,
        )
        elapsed = (_time.monotonic() - start) * 1000
        success = bool(raw_result.get("success"))
        get_health_tracker().record(request.provider, success=success, latency_ms=elapsed)
        trace = OnlineAcquisitionSourceTraceEntry(
            provider=request.provider,
            attempt=1,
            action=request.action,
            success=success,
            items_count=len(raw_result.get("items") or []),
            downloads_count=len(raw_result.get("downloads") or []),
            warnings=list(raw_result.get("warnings") or []),
        )
        return _rust_result_to_gateway(request.provider, raw_result, trace)
    except Exception as exc:
        elapsed = (_time.monotonic() - start) * 1000
        get_health_tracker().record(request.provider, success=False, latency_ms=elapsed)
        return _failure_result(request.provider, exc, request.action)


async def call_provider_with_retry(
    request: OnlineAcquisitionGatewayRequest,
    max_attempts: int = 2,
) -> OnlineAcquisitionGatewayResult:
    """Call a provider with retry logic and source_trace aggregation."""
    all_traces: List[OnlineAcquisitionSourceTraceEntry] = []
    last_result: Optional[OnlineAcquisitionGatewayResult] = None

    for attempt in range(1, max_attempts + 1):
        result = await call_provider(request)
        # Update attempt number in traces
        for trace in result.source_trace:
            trace.attempt = attempt
        all_traces.extend(result.source_trace)

        if result.success and (result.items or result.downloads):
            result.source_trace = all_traces
            return result
        last_result = result
        if attempt < max_attempts:
            await asyncio.sleep(0.5 * attempt)

    if last_result:
        last_result.source_trace = all_traces
        return last_result
    return _failure_result(request.provider, RuntimeError("no result"), request.action)


async def search_provider(
    provider: str,
    query: Optional[str] = None,
    identifiers: Optional[Dict[str, Optional[str]]] = None,
    limit: int = 20,
    raw: bool = False,
    params: Optional[Dict[str, Any]] = None,
) -> OnlineAcquisitionGatewayResult:
    """Search a single provider."""
    request = OnlineAcquisitionGatewayRequest(
        provider=provider,
        action="search",
        query=query,
        identifiers=identifiers or {},
        limit=limit,
        raw=raw,
        params=params or {},
    )
    return await call_provider_with_retry(request)


async def download_from_provider(
    provider: str,
    query: Optional[str] = None,
    identifiers: Optional[Dict[str, Optional[str]]] = None,
    limit: int = 20,
    raw: bool = False,
    download_path: str = "./downloads",
    selected_index: int = 0,
    selected_title: Optional[str] = None,
    detail_link: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
) -> OnlineAcquisitionGatewayResult:
    """Download from a provider. Handles candidate URL retrieval + actual PDF download."""
    request = OnlineAcquisitionGatewayRequest(
        provider=provider,
        action="download",
        query=query,
        identifiers=identifiers or {},
        limit=limit,
        raw=raw,
        params=params or {},
        download_path=download_path,
        selected_index=selected_index,
        selected_title=selected_title,
        detail_link=detail_link,
    )
    result = await call_provider_with_retry(request)

    # If net-io returned PDF candidate URLs, try to actually download them
    if result.success and result.downloads:
        pdf_candidates = [
            d.get("pdf_url") for d in result.downloads if d.get("pdf_url")
        ]
        if pdf_candidates:
            filename_stem = selected_title or query or "paper"
            file_path, pdf_url, dl_warnings = await _download_pdf_from_candidates(
                pdf_candidates, download_path, filename_stem
            )
            result.warnings.extend(dl_warnings)
            if file_path:
                # Replace downloads with actual file info
                result.downloads = [{"file_path": file_path, "pdf_url": pdf_url}]

    return result
