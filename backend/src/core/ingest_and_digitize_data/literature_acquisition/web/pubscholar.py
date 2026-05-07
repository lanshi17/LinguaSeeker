"""PubScholar web provider — Chinese academic literature platform."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, quote_plus, urljoin, urlparse
from html import unescape

import httpx
from bs4 import BeautifulSoup

from .base import (
    choose_item,
    download_pdf_from_candidates,
    extract_pdf_links_from_html,
    safe_json_loads,
    sanitize_filename,
    wait_for_xpath_js,
)
from .locators import (
    PUBSCHOLAR_FULLTEXT_BTN,
    PUBSCHOLAR_LANGUAGE_HEADER,
    PUBSCHOLAR_PAPER_TYPE_HEADER,
    PUBSCHOLAR_RESULTS_CONTAINER,
    PUBSCHOLAR_SEARCH_BUTTON,
    PUBSCHOLAR_SEARCH_INPUT,
)

log = logging.getLogger(__name__)

BASE_URL = "https://pubscholar.cn"
USER_AGENT = "Mozilla/5.0"


def _decode_duckduckgo_link(href: str) -> str:
    """Decode DuckDuckGo redirect URL to actual target."""
    if not href:
        return ""
    value = unescape(href)
    if value.startswith("//"):
        value = f"https:{value}"
    parsed = urlparse(value)
    if "duckduckgo.com" in (parsed.netloc or ""):
        target = parse_qs(parsed.query).get("uddg", [])
        if target:
            return target[0]
    return value


async def _duckduckgo_search(query: str, limit: int = 10) -> List[Dict[str, str]]:
    """Search via DuckDuckGo HTML endpoint."""
    if not query.strip():
        return []
    url = "https://html.duckduckgo.com/html/"
    headers = {
        "user-agent": USER_AGENT,
        "accept": "text/html,application/xhtml+xml",
        "referer": f"https://duckduckgo.com/?q={quote_plus(query)}",
    }
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(url, params={"q": query}, headers=headers)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    results: List[Dict[str, str]] = []
    seen: set[str] = set()
    for anchor in soup.select("a.result__a"):
        href = _decode_duckduckgo_link(anchor.get("href") or "")
        if not href or href in seen:
            continue
        seen.add(href)
        title = anchor.get_text(" ", strip=True) or href
        results.append({"title": title, "url": href})
        if len(results) >= limit:
            break
    return results


async def _search_via_duckduckgo(query: str, limit: int) -> List[Dict[str, Any]]:
    """Search PubScholar pages via DuckDuckGo."""
    queries = [
        f"site:pubscholar.cn/literatures {query}",
        f"site:pubscholar.cn {query}",
        f"{query} 学术 论文",
    ]
    raw_hits: List[Dict[str, str]] = []
    for q in queries:
        try:
            hits = await _duckduckgo_search(q, limit=max(limit, 8))
        except Exception:
            hits = []
        raw_hits.extend(hits)
        if len(raw_hits) >= limit:
            break

    dedup: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for hit in raw_hits:
        link = hit.get("url") or ""
        if not link or link in seen:
            continue
        seen.add(link)
        dedup.append({
            "title": hit.get("title") or link,
            "source_link": link,
            "has_full_text": True if re.search(r"\.pdf(?:$|[?#])", link, re.IGNORECASE) else None,
        })
        if len(dedup) >= limit:
            break
    return dedup


async def pubscholar_search(
    query: str,
    limit: int = 20,
    language: Optional[str] = None,
    paper_types: Optional[List[str]] = None,
    full_text_only: bool = True,
    timeout_ms: int = 80000,
) -> Dict[str, Any]:
    """Search PubScholar for papers."""
    warnings: List[str] = []

    # Try DuckDuckGo first (no browser needed)
    items = await _search_via_duckduckgo(query, limit)
    if items:
        warnings.append("fallback_search:duckduckgo")
        return {"success": True, "items": items[:limit], "warnings": warnings}

    # Fallback to crawl4ai + LLM extraction
    try:
        from crawl4ai import (
            AsyncWebCrawler,
            BrowserConfig,
            CacheMode,
            CrawlerRunConfig,
            LLMConfig,
            LLMExtractionStrategy,
        )
    except ImportError:
        warnings.append("crawl4ai_not_available")
        return {"success": False, "items": [], "warnings": warnings}

    import os
    llm_provider = os.getenv("CRAWL4AI_LLM_PROVIDER", "deepseek")
    llm_api_key = os.getenv("CRAWL4AI_LLM_API_KEY") or os.getenv("DEEPSEEK_API_KEY")

    if not llm_api_key:
        warnings.append("no_llm_api_key")
        return {"success": False, "items": [], "warnings": warnings}

    # Build JS for search interaction
    js_parts = [
        "(async () => {",
        "  const sleep = (ms) => new Promise(r => setTimeout(r, ms));",
        "  const $x = (xpath) => document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;",
        "  const click = (xpath) => { const el = $x(xpath); if (el) el.click(); return !!el; };",
        "  const input = (xpath, value) => {",
        "      const el = $x(xpath);",
        "      if (!el) return false;",
        "      el.focus(); el.value = '';",
        "      el.dispatchEvent(new Event('input', {bubbles:true}));",
        "      el.value = value;",
        "      el.dispatchEvent(new Event('input', {bubbles:true}));",
        "      return true;",
        "  };",
        "  const clickByText = (text) => {",
        "      const candidates = Array.from(document.querySelectorAll('button,span,li,div,a'))",
        "        .filter(el => el.textContent && el.textContent.trim() === text);",
        "      if (candidates.length) { candidates[0].click(); return true; }",
        "      return false;",
        "  };",
        f"  input({PUBSCHOLAR_SEARCH_INPUT!r}, {query!r});",
        f"  click({PUBSCHOLAR_SEARCH_BUTTON!r});",
        "  await sleep(1200);",
    ]

    if language:
        js_parts.extend([
            f"  click({PUBSCHOLAR_LANGUAGE_HEADER!r});",
            "  await sleep(200);",
            f"  clickByText({language!r});",
            "  await sleep(300);",
        ])

    paper_types = paper_types or []
    if paper_types:
        js_parts.extend([
            f"  click({PUBSCHOLAR_PAPER_TYPE_HEADER!r});",
            "  await sleep(200);",
        ])
        for pt in paper_types:
            js_parts.extend([f"  clickByText({pt!r});", "  await sleep(200);"])

    if full_text_only:
        js_parts.extend([
            f"  click({PUBSCHOLAR_FULLTEXT_BTN!r});",
            "  await sleep(200);",
        ])

    js_parts.extend([
        f"  const container = $x({PUBSCHOLAR_RESULTS_CONTAINER!r});",
        "  if (container) { document.body.innerHTML = container.outerHTML; }",
        "})();",
    ])
    js_code = "\n".join(js_parts)

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
                        "paper_type": {"type": "string"},
                        "language": {"type": "string"},
                        "has_full_text": {"type": "boolean"},
                        "source_link": {"type": "string"},
                        "subjects": {"type": "array", "items": {"type": "string"}},
                    },
                },
            }
        },
    }

    instruction = f"Extract at most {limit} items. Fields: title, authors, year, journal, paper_type, language, has_full_text, source_link, subjects."

    llm_strategy = LLMExtractionStrategy(
        llm_config=LLMConfig(provider=llm_provider, api_token=llm_api_key),
        schema=schema,
        extraction_type="schema",
        instruction=instruction,
        extra_args={"temperature": 0, "top_p": 0.9, "max_tokens": 2000},
    )

    browser_config = BrowserConfig(headless=True, java_script_enabled=True)
    crawler_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        js_code=[js_code],
        wait_for=wait_for_xpath_js(PUBSCHOLAR_RESULTS_CONTAINER),
        page_timeout=timeout_ms,
        word_count_threshold=1,
        extraction_strategy=llm_strategy,
    )

    items = []
    raw_excerpt = None

    try:
        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url=BASE_URL, config=crawler_config)

        if result.success:
            data = safe_json_loads(result.extracted_content)
            raw_items = []
            if isinstance(data, list):
                raw_items = [i for i in data if isinstance(i, dict)]
            elif isinstance(data, dict):
                items_val = data.get("items", [])
                if isinstance(items_val, list):
                    raw_items = [i for i in items_val if isinstance(i, dict)]

            for idx, raw in enumerate(raw_items[:limit]):
                items.append({
                    "title": raw.get("title", ""),
                    "authors": raw.get("authors"),
                    "year": raw.get("year"),
                    "journal": raw.get("journal"),
                    "paper_type": raw.get("paper_type"),
                    "language": raw.get("language"),
                    "has_full_text": raw.get("has_full_text"),
                    "source_link": raw.get("source_link"),
                    "subjects": raw.get("subjects"),
                    "index": idx,
                })

            if result.markdown:
                raw_excerpt = result.markdown[:1000]
        else:
            warnings.append(result.error_message or "crawl_failed")
    except Exception as exc:
        warnings.append(f"crawl_failed:{exc}")

    return {"success": bool(items), "items": items, "warnings": warnings, "raw_excerpt": raw_excerpt}


async def pubscholar_download(
    query: str,
    detail_link: Optional[str] = None,
    selected_index: int = 0,
    selected_title: Optional[str] = None,
    download_path: str = "./downloads",
    timeout_ms: int = 80000,
) -> Dict[str, Any]:
    """Download a paper PDF from PubScholar."""
    warnings: List[str] = []

    # 1) Get source_link
    source_link = detail_link
    if not source_link:
        search_result = await pubscholar_search(query, limit=20, timeout_ms=timeout_ms)
        if not search_result.get("success") or not search_result.get("items"):
            return {"success": False, "warnings": ["no_search_results"]}

        chosen = choose_item(search_result["items"], selected_index, selected_title)
        if not chosen:
            return {"success": False, "warnings": ["invalid_selected_index"]}
        source_link = chosen.get("source_link")

    if not source_link:
        return {"success": False, "warnings": ["missing_source_link"]}

    pdf_links: List[str] = []
    if ".pdf" in source_link.lower():
        pdf_links.append(source_link)

    # 2) Direct HTTP parse first
    if not pdf_links:
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                page = await client.get(
                    source_link,
                    headers={"user-agent": USER_AGENT, "accept": "text/html,application/xhtml+xml"},
                )
                if page.status_code < 400:
                    pdf_links.extend(extract_pdf_links_from_html(page.text, str(page.url)))
        except Exception as exc:
            warnings.append(f"http_parse_failed:{exc}")

    # 3) Browser fallback
    if not pdf_links:
        try:
            from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig

            browser_config = BrowserConfig(headless=True, java_script_enabled=True)
            crawler_config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)
            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(url=source_link, config=crawler_config)
                if result.success:
                    pdf_links.extend(extract_pdf_links_from_html(result.cleaned_html, source_link))
        except Exception as exc:
            warnings.append(f"crawl_parse_failed:{exc}")

    # 4) DuckDuckGo PDF search fallback
    if not pdf_links:
        search_query = selected_title or query
        try:
            hits = await _duckduckgo_search(f"{search_query} filetype:pdf", limit=10)
            for hit in hits:
                url = hit.get("url") or ""
                if re.search(r"\.pdf(?:$|[?#])", url, re.IGNORECASE):
                    pdf_links.append(url)
            if pdf_links:
                warnings.append("fallback_pdf:duckduckgo")
        except Exception as exc:
            warnings.append(f"pdf_search_failed:{exc}")

    if not pdf_links:
        return {"success": False, "warnings": warnings + ["pdf_not_found"]}

    file_path, final_url, dl_warnings = await download_pdf_from_candidates(
        pdf_links, download_path, selected_title or query
    )
    warnings.extend(dl_warnings)

    if not file_path:
        return {"success": False, "warnings": warnings + ["download_failed"]}

    return {"success": True, "pdf_url": final_url, "file_path": file_path, "warnings": warnings}
