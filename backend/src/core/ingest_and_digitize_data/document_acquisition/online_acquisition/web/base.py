"""Shared utilities for web providers."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

import httpx
from selectolax.parser import HTMLParser


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
    """Extract PDF links from HTML. Uses Rust parser when available, falls back to selectolax."""
    if not html:
        return []
    try:
        import rust_io.literature as literature_io
        return literature_io.extract_pdf_links(html, base_url)
    except (ImportError, Exception):
        pass
    # Fallback: selectolax
    tree = HTMLParser(html)
    links = []
    for node in tree.css("a[href]"):
        href = (node.attributes.get("href") or "").strip()
        if ".pdf" in href.lower():
            links.append(urljoin(base_url, href))
    for node in tree.css("meta[name='citation_pdf_url']"):
        content = (node.attributes.get("content") or "").strip()
        if content:
            links.append(urljoin(base_url, content))
    return list(dict.fromkeys(links))


def scrape_html_elements(html: str, css_selector: str) -> List[Dict[str, Any]]:
    """Parse HTML with CSS selector. Uses Rust when available, falls back to selectolax."""
    if not html:
        return []
    try:
        import rust_io.literature as literature_io
        return literature_io.scrape_html(html, css_selector)
    except (ImportError, Exception):
        pass
    # Fallback: selectolax
    tree = HTMLParser(html)
    return [
        {
            "text": node.text(deep=True, separator=" ").strip(),
            "html": node.html,
            "tag_name": node.tag,
            "attrs": dict(node.attributes) if node.attributes else {},
        }
        for node in tree.css(css_selector)
    ]


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


def build_js_helpers() -> str:
    """Return JavaScript helper functions for UI interaction."""
    return """
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  const $x = (xpath) => document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
  const click = (xpath) => { const el = $x(xpath); if (el) el.click(); return !!el; };
  const input = (xpath, value) => {
      const el = $x(xpath);
      if (!el) return false;
      el.focus(); el.value = '';
      el.dispatchEvent(new Event('input', {bubbles:true}));
      el.value = value;
      el.dispatchEvent(new Event('input', {bubbles:true}));
      return true;
  };
  const clickByText = (text) => {
      const candidates = Array.from(document.querySelectorAll('button,span,li,div,a,label'))
        .filter(el => el.textContent && el.textContent.trim() === text);
      if (candidates.length) { candidates[0].click(); return true; }
      const fuzzy = Array.from(document.querySelectorAll('button,span,li,div,a,label'))
        .filter(el => el.textContent && el.textContent.includes(text));
      if (fuzzy.length) { fuzzy[0].click(); return true; }
      return false;
  };
"""


def resolve_llm_config() -> Tuple[str, Optional[str]]:
    """Resolve LLM provider and API key with hierarchical fallback.

    Checks project config first, then env vars.
    Returns (provider, api_key).
    """
    # Try project config first
    try:
        from src.config import get_settings, resolve_llm_triplet
        settings = get_settings()
        triplet = resolve_llm_triplet(settings, "retrieval")
        if triplet.api_key:
            provider = "deepseek"
            if "openai" in triplet.base_url.lower():
                provider = "openai"
            elif "anthropic" in triplet.base_url.lower():
                provider = "anthropic"
            elif "dashscope" in triplet.base_url.lower():
                provider = "dashscope"
            return provider, triplet.api_key
    except (ImportError, Exception):
        pass

    # Fallback to env vars
    provider = os.getenv("CRAWL4AI_LLM_PROVIDER", "deepseek")
    api_key = os.getenv("CRAWL4AI_LLM_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
    return provider, api_key


async def crawl4ai_search(
    url: str,
    js_code: str,
    wait_xpath: str,
    schema: Dict[str, Any],
    instruction: str,
    limit: int,
    timeout_ms: int = 80000,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Shared crawl4ai search flow. Returns (items, warnings)."""
    warnings: List[str] = []

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
        return [], warnings

    provider, api_key = resolve_llm_config()
    if not api_key:
        warnings.append("no_llm_api_key")
        return [], warnings

    llm_strategy = LLMExtractionStrategy(
        llm_config=LLMConfig(provider=provider, api_token=api_key),
        schema=schema,
        extraction_type="schema",
        instruction=instruction,
        extra_args={"temperature": 0, "top_p": 0.9, "max_tokens": 2000},
    )

    browser_config = BrowserConfig(headless=True, java_script_enabled=True)
    crawler_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        js_code=[js_code],
        wait_for=wait_for_xpath_js(wait_xpath),
        page_timeout=timeout_ms,
        word_count_threshold=1,
        extraction_strategy=llm_strategy,
    )

    try:
        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url=url, config=crawler_config)
    except Exception as exc:
        warnings.append(f"crawl_failed:{exc}")
        return [], warnings

    if not result.success:
        warnings.append(result.error_message or "crawl_failed")
        return [], warnings

    data = safe_json_loads(result.extracted_content)
    raw_items: List[Dict[str, Any]] = []
    if isinstance(data, list):
        raw_items = [i for i in data if isinstance(i, dict)]
    elif isinstance(data, dict):
        items_val = data.get("items", [])
        if isinstance(items_val, list):
            raw_items = [i for i in items_val if isinstance(i, dict)]

    return raw_items[:limit], warnings
