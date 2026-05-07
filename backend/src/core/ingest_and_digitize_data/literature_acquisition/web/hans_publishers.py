"""Hans Publishers web provider — Chinese open-access publisher."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import (
    choose_item,
    download_pdf_from_candidates,
    extract_pdf_links_from_html,
    sanitize_filename,
    safe_json_loads,
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
    subjects = subjects or []

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

    query_str = " ".join(query) if isinstance(query, list) else query

    js_code = f"""
    (async () => {{
      const sleep = (ms) => new Promise(r => setTimeout(r, ms));
      const $x = (xpath) => document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
      const click = (xpath) => {{ const el = $x(xpath); if (el) el.click(); return !!el; }};
      const input = (xpath, value) => {{
          const el = $x(xpath);
          if (!el) return false;
          el.focus(); el.value = '';
          el.dispatchEvent(new Event('input', {{bubbles:true}}));
          el.value = value;
          el.dispatchEvent(new Event('input', {{bubbles:true}}));
          return true;
      }};
      const clickByText = (text) => {{
          const nodes = Array.from(document.querySelectorAll('a,button,li,span,label,div'))
            .filter(el => el.textContent && el.textContent.trim() === text);
          if (nodes.length) {{ nodes[0].click(); return true; }}
          return false;
      }};

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

    llm_strategy = LLMExtractionStrategy(
        llm_config=LLMConfig(provider=llm_provider, api_token=llm_api_key),
        schema=schema,
        extraction_type="schema",
        instruction=instruction,
        extra_args={"temperature": 0, "max_tokens": 2000},
    )

    browser_config = BrowserConfig(headless=True, java_script_enabled=True)
    crawler_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        js_code=[js_code],
        wait_for=f"""() => !!document.evaluate({HANS_RESULTS_CONTAINER!r}, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue""",
        page_timeout=timeout_ms,
        word_count_threshold=1,
        extraction_strategy=llm_strategy,
    )

    items: List[Dict[str, Any]] = []

    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(url=BASE_URL, config=crawler_config)

    if result.success:
        data = safe_json_loads(result.extracted_content)
        raw_items: List[Dict[str, Any]] = []
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
                "subject": raw.get("subject"),
                "detail_link": raw.get("detail_link"),
                "index": idx,
            })

        if not items:
            # Fallback: extract from HTML
            cleaned_html = getattr(result, "cleaned_html", None) or ""
            items = _fallback_extract_items_from_html(cleaned_html, limit)
            if items:
                warnings.append("fallback_html_items_used")
    else:
        warnings.append(result.error_message or "crawl_failed")

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

        wait_js = f"""() => !!document.evaluate({HANS_PDF_LINK!r}, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue"""

        browser_config = BrowserConfig(headless=True, java_script_enabled=True)
        crawler_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            wait_for=wait_js,
            page_timeout=timeout_ms,
        )

        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url=detail_link, config=crawler_config)

        if result.success:
            pdf_links = extract_pdf_links_from_html(result.cleaned_html, detail_link)
            if pdf_links:
                pdf_url = pdf_links[0]
    except ImportError:
        # crawl4ai not available, try httpx
        import httpx
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                page = await client.get(detail_link, headers={"user-agent": USER_AGENT})
                page.raise_for_status()
                pdf_links = extract_pdf_links_from_html(page.text, detail_link)
                if pdf_links:
                    pdf_url = pdf_links[0]
        except Exception as exc:
            warnings.append(f"http_parse_failed:{exc}")
    except Exception as exc:
        warnings.append(f"crawl_failed:{exc}")

    if not pdf_url:
        return {"success": False, "warnings": warnings + ["pdf_not_found"]}

    file_path, final_url, dl_warnings = await download_pdf_from_candidates(
        [pdf_url], download_path, selected_title or query, referer=detail_link
    )
    warnings.extend(dl_warnings)

    if not file_path:
        return {"success": False, "warnings": warnings + ["download_failed"]}

    return {"success": True, "pdf_url": final_url, "file_path": file_path, "warnings": warnings}
