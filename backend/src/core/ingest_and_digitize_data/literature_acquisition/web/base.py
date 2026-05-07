"""Shared utilities for web providers."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup


def safe_json_loads(text: str) -> Any:
    """Parse JSON, extracting from mixed content if needed."""
    if not text:
        return {}
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"(\{.*\}|\[.*\])", text, re.S)
        if match:
            return json.loads(match.group(1))
    return {}


def sanitize_filename(name: str) -> str:
    """Sanitize filename by removing invalid characters."""
    name = re.sub(r'[\\/:*?"<>|]+', "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    return (name or "paper")[:120]


def extract_pdf_links_from_html(html: str, base_url: str) -> List[str]:
    """Extract PDF links from HTML using BeautifulSoup."""
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if ".pdf" in href.lower():
            links.append(urljoin(base_url, href))
    for meta in soup.find_all("meta"):
        name = (meta.get("name") or "").lower()
        if name == "citation_pdf_url":
            content = (meta.get("content") or "").strip()
            if content:
                links.append(urljoin(base_url, content))
    return list(dict.fromkeys(links))


def choose_item(
    items: List[Dict[str, Any]], selected_index: int, selected_title: Optional[str]
) -> Optional[Dict[str, Any]]:
    """Choose an item from search results by index or title."""
    if selected_title:
        for it in items:
            if selected_title.lower() in (it.get("title") or "").lower():
                return it
    if 0 <= selected_index < len(items):
        return items[selected_index]
    return None


async def download_pdf_from_candidates(
    candidates: List[str],
    download_path: str,
    filename_stem: str,
    referer: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str], List[str]]:
    """Download PDF from candidate URLs with %PDF header validation."""
    warnings: List[str] = []
    queue = [c for c in candidates if c]
    visited: set[str] = set()
    os.makedirs(download_path, exist_ok=True)
    filename = sanitize_filename(filename_stem) + ".pdf"
    file_path = os.path.join(download_path, filename)

    headers = {"user-agent": "Mozilla/5.0", "accept": "*/*"}
    if referer:
        headers["referer"] = referer

    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            try:
                resp = await client.get(current, headers=headers)
                if resp.status_code >= 400:
                    warnings.append(f"download_http_{resp.status_code}:{current}")
                    continue
                content = resp.content
                if content.startswith(b"%PDF"):
                    with open(file_path, "wb") as f:
                        f.write(content)
                    return file_path, str(resp.url), warnings
                ctype = (resp.headers.get("content-type") or "").lower()
                if "html" in ctype or b"<html" in content[:2048].lower():
                    extra = extract_pdf_links_from_html(resp.text or "", str(resp.url))
                    for link in extra:
                        if link not in visited:
                            queue.append(link)
            except Exception as exc:
                warnings.append(f"download_probe_failed:{current}:{exc}")

    return None, None, warnings


def wait_for_xpath_js(xpath: str) -> str:
    """Build JavaScript wait condition for XPath."""
    return f"""() => !!document.evaluate({json.dumps(xpath)}, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue"""
