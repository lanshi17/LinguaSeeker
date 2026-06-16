"""CyberLeninka web provider — Russian open-access repository."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote_plus, urljoin

import httpx

from .base import (
    build_js_helpers,
    choose_item,
    crawl4ai_search,
    download_pdf_from_candidates,
    extract_pdf_links_from_html,
)
from .locators import (
    CYBERLENINKA_RESULTS,
    CYBERLENINKA_SEARCH_BUTTON,
    CYBERLENINKA_SEARCH_INPUT,
)

log = logging.getLogger(__name__)

BASE_URL = "https://cyberleninka.ru"
USER_AGENT = "Mozilla/5.0"


def _strip_tags(value: str) -> str:
    return re.sub(r"<[^>]+>", "", value or "").strip()


async def _search_via_api(
    query: str, subjects: List[str], limit: int
) -> List[Dict[str, Any]]:
    """Search via CyberLeninka's public JSON API."""
    if not query.strip():
        return []

    payload: Dict[str, Any] = {
        "mode": "articles",
        "q": query,
        "size": min(limit, 50),
        "from": 0,
    }
    if subjects:
        payload["catalogs"] = subjects

    headers = {
        "user-agent": USER_AGENT,
        "accept": "application/json, text/plain, */*",
        "content-type": "application/json",
        "referer": f"{BASE_URL}/search?q={quote_plus(query)}",
    }

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.post(f"{BASE_URL}/api/search", json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    raw_items = data.get("articles") if isinstance(data, dict) else []
    if not isinstance(raw_items, list):
        return []

    items: List[Dict[str, Any]] = []
    for idx, raw in enumerate(raw_items[:limit]):
        if not isinstance(raw, dict):
            continue
        title = _strip_tags(str(raw.get("name") or "")) or "Untitled"
        authors_raw = raw.get("authors")
        authors = None
        if isinstance(authors_raw, list):
            authors = ", ".join([str(a) for a in authors_raw if a])
        elif isinstance(authors_raw, str):
            authors = authors_raw

        detail_link = raw.get("link")
        if detail_link:
            detail_link = urljoin(BASE_URL + "/", str(detail_link))

        catalogs = raw.get("catalogs")
        subject = None
        if isinstance(catalogs, list):
            parts = []
            for entry in catalogs:
                if isinstance(entry, dict):
                    name = entry.get("name") or entry.get("title") or entry.get("label")
                    if name:
                        parts.append(str(name))
                elif entry:
                    parts.append(str(entry))
            subject = ", ".join(parts) if parts else None

        items.append({
            "title": title,
            "authors": authors,
            "year": str(raw.get("year")) if raw.get("year") else None,
            "journal": raw.get("journal"),
            "subject": subject,
            "detail_link": detail_link,
            "index": idx,
        })

    return items


async def _search_via_crawl4ai(
    query: str, subjects: List[str], limit: int, timeout_ms: int
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Search via crawl4ai browser automation (fallback). Uses shared helper."""
    js_code = f"""
    (async () => {{
      {build_js_helpers()}
      input({CYBERLENINKA_SEARCH_INPUT!r}, {query!r});
      click({CYBERLENINKA_SEARCH_BUTTON!r});
      await sleep(1200);
      const container = $x({CYBERLENINKA_RESULTS!r});
      if (container) {{ document.body.innerHTML = container.outerHTML; }}
    }})();
    """

    schema = {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "authors": {"type": "string"},
                        "year": {"type": "string"},
                        "journal": {"type": "string"},
                        "detail_link": {"type": "string"},
                    },
                },
            }
        },
    }

    instruction = f"Extract up to {limit} papers. Return JSON with key 'items'. Fields: title, authors, year, journal, detail_link."

    items, warnings = await crawl4ai_search(
        url=BASE_URL,
        js_code=js_code,
        wait_xpath=CYBERLENINKA_RESULTS,
        schema=schema,
        instruction=instruction,
        limit=limit,
        timeout_ms=timeout_ms,
    )
    return items, warnings


async def cyberleninka_search(
    query: str,
    limit: int = 20,
    subjects: Optional[List[str]] = None,
    timeout_ms: int = 80000,
) -> Dict[str, Any]:
    """Search CyberLeninka for papers."""
    warnings: List[str] = []
    subjects = subjects or []

    # Try public API first
    items = await _search_via_api(query, subjects, limit)
    if items:
        return {"success": True, "items": items, "warnings": warnings}

    # Fallback to crawl4ai
    warnings.append("api_search_failed:falling_back_to_crawl4ai")
    items, crawl_warnings = await _search_via_crawl4ai(query, subjects, limit, timeout_ms)
    warnings.extend(crawl_warnings)
    if items:
        return {"success": True, "items": items, "warnings": warnings}

    warnings.append("all_search_methods_failed")
    return {"success": False, "items": [], "warnings": warnings}


async def cyberleninka_download(
    query: str,
    detail_link: Optional[str] = None,
    selected_index: int = 0,
    selected_title: Optional[str] = None,
    download_path: str = "./downloads",
    timeout_ms: int = 80000,
) -> Dict[str, Any]:
    """Download a paper PDF from CyberLeninka."""
    warnings: List[str] = []

    if not detail_link:
        search_result = await cyberleninka_search(query, limit=20, timeout_ms=timeout_ms)
        if not search_result.get("success") or not search_result.get("items"):
            return {"success": False, "warnings": ["no_search_results"]}

        chosen = choose_item(search_result["items"], selected_index, selected_title)
        if not chosen:
            return {"success": False, "warnings": ["invalid_selected_index"]}
        detail_link = chosen.get("detail_link")

    if not detail_link:
        return {"success": False, "warnings": ["missing_detail_link"]}

    # Fetch detail page and extract PDF link
    pdf_url = None
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            page = await client.get(detail_link, headers={"user-agent": USER_AGENT, "referer": BASE_URL})
            page.raise_for_status()
            pdf_links = extract_pdf_links_from_html(page.text, detail_link)
            if pdf_links:
                pdf_url = pdf_links[0]
    except Exception as exc:
        warnings.append(f"detail_fetch_failed:{exc}")

    # Try /pdf endpoint
    if not pdf_url:
        pdf_candidate = f"{detail_link.rstrip('/')}/pdf"
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                probe = await client.get(pdf_candidate)
                if probe.status_code < 400 and probe.content.startswith(b"%PDF"):
                    pdf_url = str(probe.url)
        except Exception:
            pass

    if not pdf_url:
        return {"success": False, "warnings": warnings + ["pdf_not_found"]}

    file_path, final_url, dl_warnings = await download_pdf_from_candidates(
        [pdf_url], download_path, selected_title or query, referer=detail_link
    )
    warnings.extend(dl_warnings)

    if not file_path:
        return {"success": False, "warnings": warnings + ["download_failed"]}

    return {"success": True, "pdf_url": final_url, "file_path": file_path, "warnings": warnings}
