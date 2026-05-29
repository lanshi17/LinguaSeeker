"""DOI landing page probe and PDF download fallback (async)."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import httpx

from src.utils.text import sanitize_filename

_PDF_LINK_PATTERNS = [
    re.compile(r'href=["\']([^"\']*\.pdf[^"\']*)["\']', re.IGNORECASE),
    re.compile(r'href=["\']([^"\']*download[^"\']*pdf[^"\']*)["\']', re.IGNORECASE),
]

_CHINESE_DOMAINS = {"yiigle.com", "wanfangdata.com.cn", "cnki.net", "cqvip.com"}

_TIMEOUT = 60

_BROWSER_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf;q=0.8,*/*;q=0.7",
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,ja;q=0.7",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36 ACMG-Lingua/1.0",
}


def _normalize_proxy_url(proxy: Optional[str]) -> Optional[str]:
    value = str(proxy or "").strip()
    if value.lower() in {"", "none", "false", "off", "0"}:
        return None
    if "://" not in value:
        value = f"http://{value}"
    return value


def _extract_pdf_links(html: str, base_url: str) -> List[str]:
    links: List[str] = []
    for pattern in _PDF_LINK_PATTERNS:
        for match in pattern.finditer(html):
            href = match.group(1)
            absolute = urljoin(base_url, href)
            if absolute not in links:
                links.append(absolute)
    return links


def _is_chinese_domain(url: str) -> bool:
    lower = url.lower()
    return any(domain in lower for domain in _CHINESE_DOMAINS)


async def probe_doi_landing_page(
    doi: str,
    *,
    timeout: int = _TIMEOUT,
    email: Optional[str] = None,
    proxy: Optional[str] = None,
) -> Dict[str, Any]:
    """Probe a DOI landing page to find a direct PDF link."""
    ua = _BROWSER_HEADERS["User-Agent"]
    if email:
        ua = f"{ua} (+mailto:{email})"
    headers = {**_BROWSER_HEADERS, "User-Agent": ua}

    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            proxy=_normalize_proxy_url(proxy),
        ) as client:
            landing = await client.get(f"https://doi.org/{doi}", headers=headers)
    except Exception as exc:
        return {"success": False, "pdf_url": None, "error": str(exc), "warnings": [f"doi_probe_failed:{exc}"]}

    if not landing.is_success:
        return {
            "success": False,
            "pdf_url": None,
            "error": f"HTTP {landing.status_code}",
            "warnings": [f"doi_probe_http_{landing.status_code}"],
        }

    resolved_url = str(landing.url)

    if landing.content.startswith(b"%PDF"):
        return {"success": True, "pdf_url": resolved_url, "resolved_url": resolved_url, "warnings": []}

    if _is_chinese_domain(resolved_url):
        # Return partial success — DOI resolves, but PDF requires institutional access
        return {
            "success": True,
            "pdf_url": None,
            "resolved_url": resolved_url,
            "is_chinese": True,
            "warnings": ["chinese_domain_no_direct_pdf"],
        }

    pdf_links = _extract_pdf_links(landing.text or "", resolved_url)
    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        proxy=_normalize_proxy_url(proxy),
    ) as client:
        for link in pdf_links:
            try:
                probe = await client.get(link, headers=headers)
                if probe.is_success and probe.content.startswith(b"%PDF"):
                    return {"success": True, "pdf_url": link, "resolved_url": resolved_url, "warnings": []}
            except Exception:
                continue

    return {"success": False, "pdf_url": None, "resolved_url": resolved_url, "warnings": ["doi_probe_no_pdf_found"]}


async def doi_fallback_download(
    doi: str,
    *,
    download_path: str = "./downloads",
    email: Optional[str] = None,
    timeout: int = _TIMEOUT,
    proxy: Optional[str] = None,
) -> Dict[str, Any]:
    """Try to download a PDF via DOI landing page probe."""
    warnings: List[str] = []

    probe = await probe_doi_landing_page(doi, timeout=timeout, email=email, proxy=proxy)
    warnings.extend(probe.get("warnings") or [])

    if probe.get("is_chinese") and probe.get("resolved_url"):
        return {
            "success": True,
            "method": "doi_chinese_domain",
            "is_chinese": True,
            "resolved_url": probe["resolved_url"],
            "pdf_url": None,
            "warnings": warnings,
        }

    if probe.get("success") and probe.get("pdf_url"):
        try:
            os.makedirs(download_path, exist_ok=True)
            filename = sanitize_filename(doi.replace("/", "_")) + ".pdf"
            file_path = os.path.join(download_path, filename)
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
                proxy=_normalize_proxy_url(proxy),
            ) as client:
                resp = await client.get(probe["pdf_url"], headers=_BROWSER_HEADERS)
            if resp.is_success and resp.content.startswith(b"%PDF"):
                Path(file_path).write_bytes(resp.content)
                return {
                    "success": True,
                    "method": "doi_landing_probe",
                    "pdf_url": probe["pdf_url"],
                    "file_path": file_path,
                    "size_bytes": len(resp.content),
                    "warnings": warnings,
                }
        except Exception as exc:
            warnings.append(f"doi_download_failed:{exc}")

    return {"success": False, "method": None, "warnings": warnings}
