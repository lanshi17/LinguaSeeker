"""Unified gateway — delegates HTTP I/O to net_io, Python handles downloads."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

import httpx
import time as _time
from loguru import logger

from .provider_health import get_health_tracker

from src.core.config import get_config
from src.utils.rust_io import net_io
from src.utils.text import sanitize_filename

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
    target = Path(download_path) / f"{sanitize_filename(filename_stem)}.pdf"
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


async def download_file_from_url(
    url: str,
    download_path: str,
    filename_stem: str,
) -> Tuple[Optional[str], Optional[str], List[str]]:
    """Download a file from a direct URL. Handles HTML→PDF redirect.

    If the URL returns PDF bytes (magic ``%PDF``), saves directly.
    If the URL returns HTML, extracts PDF links from the page and retries
    each candidate (preserves existing _download_pdf_from_candidates behavior).

    Proxy routing: international sites go through the configured proxy;
    mainland China sites connect directly (see ``NetworkConfig``).

    Args:
        url: Direct download URL.
        download_path: Directory to save the file.
        filename_stem: Base filename (without extension).

    Returns:
        (file_path, final_url, warnings) tuple.
    """
    warnings: List[str] = []
    target = Path(download_path) / f"{sanitize_filename(filename_stem)}.pdf"
    target.parent.mkdir(parents=True, exist_ok=True)
    proxy_resolver = get_config().network.resolve_proxy_for_url

    # Build candidate queue: start with the given URL
    queue: List[str] = [url]
    visited: set[str] = set()

    while queue:
        current_url = queue.pop(0)
        if current_url in visited:
            continue
        visited.add(current_url)
        proxy = proxy_resolver(current_url)

        # Try Rust download first (faster, has built-in retry)
        if net_io is not None:
            try:
                result = await net_io.download_file(current_url, timeout_ms=30_000, proxy=proxy)
                status = result.get("status_code", 0)
                file_bytes: bytes = result.get("bytes", b"")
                final_url: str = result.get("final_url", current_url)

                if status == 0 or status >= 400:
                    warnings.append(f"download_http_{status}:{current_url}")
                    continue

                if file_bytes and file_bytes[:4] == b"%PDF":
                    target.write_bytes(file_bytes)
                    return str(target), final_url, warnings

                # Non-PDF content — might be HTML with PDF link
                if file_bytes and (b"<html" in file_bytes[:2048].lower()):
                    extra_links = _extract_pdf_links_from_html(
                        file_bytes.decode("utf-8", errors="replace"), final_url or current_url
                    )
                    for link in extra_links:
                        if link not in visited:
                            queue.append(link)
                    continue

                warnings.append(f"non_pdf_content:{current_url}")
                continue

            except Exception as exc:
                logger.debug("rust download_file failed for {}: {}", current_url, exc)
                warnings.append(f"rust_download_error:{current_url}:{exc}")
                # Fall through to httpx fallback

        # Fallback: httpx (handles HTML→PDF redirect same as existing code)
        try:
            async with httpx.AsyncClient(
                proxy=proxy, timeout=60, follow_redirects=True
            ) as client:
                resp = await client.get(current_url)
                resp.raise_for_status()

                content = resp.content or b""
                content_type = str(resp.headers.get("content-type") or "").lower()
                final_url = str(resp.url)

                if content.startswith(b"%PDF"):
                    target.write_bytes(content)
                    return str(target), final_url, warnings

                if "html" in content_type or b"<html" in content[:2048].lower():
                    extra_links = _extract_pdf_links_from_html(resp.text or "", final_url or current_url)
                    for link in extra_links:
                        if link not in visited:
                            queue.append(link)
                    continue

                warnings.append(f"non_pdf_content_type:{content_type or 'unknown'}:{current_url}")

        except Exception as exc:
            warnings.append(f"download_error:{current_url}:{exc}")

    return None, None, warnings


def resolve_oa_url(result: OnlineAcquisitionGatewayResult) -> Optional[str]:
    """Extract OA download URL from a gateway result.

    Inspects result.downloads for pdf_url entries (returned by unpaywall, doaj, etc.)
    and result.items for embedded download links (e.g., europepmc fullTextUrlList).
    """
    # Check downloads first (unpaywall, doaj, jstage pattern)
    for dl in result.downloads:
        if isinstance(dl, dict):
            dl_url = dl.get("pdf_url") or dl.get("url")
            if dl_url:
                return dl_url

    # Check items for embedded URLs (europepmc fullTextUrlList, crossref link)
    for item in result.items:
        if not isinstance(item, dict):
            continue
        # EuropePMC fullTextUrlList
        ftl = item.get("fullTextUrlList")
        if isinstance(ftl, dict):
            for ft in ftl.get("fullTextUrl", []):
                if isinstance(ft, dict) and ft.get("documentStyle") == "pdf":
                    return ft.get("url")
        # Crossref link array
        links = item.get("link")
        if isinstance(links, list):
            for link in links:
                if isinstance(link, dict) and link.get("content-type") == "application/pdf":
                    return link.get("URL")
        # PMC pmcid → construct URL
        pmcid = item.get("pmcid")
        if isinstance(pmcid, str) and pmcid.startswith("PMC"):
            return f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf/"

    return None


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
    # Pass through extra provider params (year_range, is_oa, etc.)
    if request.params:
        for k, v in request.params.items():
            if k not in params:
                params[k] = v
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
    start = _time.monotonic()
    if net_io is None:
        elapsed = (_time.monotonic() - start) * 1000
        get_health_tracker().record(request.provider, success=False, latency_ms=elapsed)
        return _failure_result(
            request.provider,
            RuntimeError("net_io not available"),
            request.action,
        )

    params = _build_fetch_params(request)
    # Provider APIs are mostly international — use the configured proxy.
    proxy = get_config().network.proxy or None
    try:
        raw_result = await net_io.fetch_one(
            provider=request.provider,
            action=request.action,
            params=params,
            proxy=proxy,
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
