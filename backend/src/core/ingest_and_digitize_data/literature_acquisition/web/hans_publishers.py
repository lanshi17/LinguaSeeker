"""Hans Publishers web provider — Chinese open-access publisher."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from .base import (
    build_js_helpers,
    choose_item,
    crawl4ai_search,
    download_pdf_from_candidates,
    extract_pdf_links_from_html,
    wait_for_xpath_js,
)
from .locators import (
    HANS_PDF_LINK,
    HANS_RESULTS_CONTAINER,
    HANS_SEARCH_BUTTON,
    HANS_SEARCH_INPUT,
)

log = logging.getLogger(__name__)

BASE_URL = "https://www.hanspub.org"
USER_AGENT = "Mozilla/5.0"


def _fallback_extract_items_from_html(html_text: str, limit: int) -> List[Dict[str, Any]]:
    """Extract items from HTML by parsing paperinformation links."""
    soup = BeautifulSoup(html_text or "", "html.parser")
    seen_links: set[str] = set()
    items: List[Dict[str, Any]] = []
    for a in soup.find_all("a", href=True):
        href = str(a.get("href") or "").strip()
        if "paperinformation?paperid=" not in href:
            continue
        detail_link = urljoin(BASE_URL, href)
        if detail_link in seen_links:
            continue
        seen_links.add(detail_link)
        title = re.sub(r"\s+", " ", a.get_text(" ", strip=True)).strip()
        if not title:
            title = f"Hans Paper {len(items) + 1}"
        items.append({
            "title": title,
            "authors": None,
            "year": None,
            "journal": None,
            "subject": None,
            "detail_link": detail_link,
            "index": len(items),
        })
        if len(items) >= max(1, limit):
            break
    return items


async def hanspub_search(
    query: str,
    limit: int = 20,
    subjects: Optional[List[str]] = None,
    timeout_ms: int = 80000,
) -> Dict[str, Any]:
    """Search Hans Publishers for papers."""
    warnings: List[str] = []
    query_str = " ".join(query) if isinstance(query, list) else query

    js_code = f"""
    (async () => {{
      {build_js_helpers()}
      input({HANS_SEARCH_INPUT!r}, {query_str!r});
      click({HANS_SEARCH_BUTTON!r});
      await sleep(1200);
      const container = $x({HANS_RESULTS_CONTAINER!r});
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
                        "subject": {"type": "string"},
                        "detail_link": {"type": "string"},
                    },
                },
            }
        },
    }

    instruction = f"Extract up to {limit} papers. Return JSON with key 'items'. Fields: title, authors, year, journal, subject, detail_link."

    raw_items, crawl_warnings = await crawl4ai_search(
        url=BASE_URL,
        js_code=js_code,
        wait_xpath=HANS_RESULTS_CONTAINER,
        schema=schema,
        instruction=instruction,
        limit=limit,
        timeout_ms=timeout_ms,
    )
    warnings.extend(crawl_warnings)

    items: List[Dict[str, Any]] = []
    for idx, raw in enumerate(raw_items):
        items.append({
            "title": raw.get("title", ""),
            "authors": raw.get("authors"),
            "year": raw.get("year"),
            "journal": raw.get("journal"),
            "subject": raw.get("subject"),
            "detail_link": raw.get("detail_link"),
            "index": idx,
        })

    if not items and not crawl_warnings:
        # Fallback: try static HTML extraction
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(BASE_URL, headers={"user-agent": USER_AGENT})
                resp.raise_for_status()
                items = _fallback_extract_items_from_html(resp.text, limit)
                if items:
                    warnings.append("fallback_html_items_used")
        except Exception as exc:
            warnings.append(f"html_fallback_failed:{exc}")

    return {"success": bool(items), "items": items, "warnings": warnings}


async def hanspub_download(
    query: str,
    detail_link: Optional[str] = None,
    selected_index: int = 0,
    selected_title: Optional[str] = None,
    download_path: str = "./downloads",
    timeout_ms: int = 80000,
) -> Dict[str, Any]:
    """Download a paper PDF from Hans Publishers."""
    warnings: List[str] = []

    if not detail_link:
        search_result = await hanspub_search(query, limit=20, timeout_ms=timeout_ms)
        if not search_result.get("success") or not search_result.get("items"):
            return {"success": False, "warnings": ["no_search_results"]}

        chosen = choose_item(search_result["items"], selected_index, selected_title)
        if not chosen:
            return {"success": False, "warnings": ["invalid_selected_index"]}
        detail_link = chosen.get("detail_link")

    if not detail_link:
        return {"success": False, "warnings": ["missing_detail_link"]}

    # Crawl detail page for PDF
    pdf_url = None
    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig

        browser_config = BrowserConfig(headless=True, java_script_enabled=True)
        crawler_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            wait_for=wait_for_xpath_js(HANS_PDF_LINK),
            page_timeout=timeout_ms,
        )

        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url=detail_link, config=crawler_config)

        if result.success:
            pdf_links = extract_pdf_links_from_html(result.cleaned_html, detail_link)
            if pdf_links:
                pdf_url = pdf_links[0]
    except ImportError:
        pass  # crawl4ai not available, fall through to httpx
    except Exception as exc:
        warnings.append(f"crawl_failed:{exc}")

    # Fallback: httpx static parse
    if not pdf_url:
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                page = await client.get(detail_link, headers={"user-agent": USER_AGENT})
                page.raise_for_status()
                pdf_links = extract_pdf_links_from_html(page.text, detail_link)
                if pdf_links:
                    pdf_url = pdf_links[0]
        except Exception as exc:
            warnings.append(f"http_parse_failed:{exc}")

    if not pdf_url:
        return {"success": False, "warnings": warnings + ["pdf_not_found"]}

    file_path, final_url, dl_warnings = await download_pdf_from_candidates(
        [pdf_url], download_path, selected_title or query, referer=detail_link
    )
    warnings.extend(dl_warnings)

    if not file_path:
        return {"success": False, "warnings": warnings + ["download_failed"]}

    return {"success": True, "pdf_url": final_url, "file_path": file_path, "warnings": warnings}
