# src/domain/literature/cyberleninka/service.py
"""CyberLeninka service implementation."""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from crawl4ai import (
    AsyncWebCrawler,
    BrowserConfig,
    CacheMode,
    CrawlerRunConfig,
    LLMConfig,
    LLMExtractionStrategy,
)

try:
    from .locators import (
        XPATH_DOWNLOAD_BTN,
        XPATH_RESULTS,
        XPATH_SEARCH_BUTTON,
        XPATH_SEARCH_INPUT,
        XPATH_SUBJECT_FILTER,
    )
    from .models import (
        BASE_URL,
        CyberleninkaPayload,
        DownloadResponse,
        PaperItem,
        PaperList,
        SearchResponse,
    )
except ImportError:
    from locators import (
        XPATH_DOWNLOAD_BTN,
        XPATH_RESULTS,
        XPATH_SEARCH_BUTTON,
        XPATH_SEARCH_INPUT,
        XPATH_SUBJECT_FILTER,
    )
    from models import (
        BASE_URL,
        CyberleninkaPayload,
        DownloadResponse,
        PaperItem,
        PaperList,
        SearchResponse,
    )

log = logging.getLogger(__name__)


def _safe_json_loads(text: str) -> Dict[str, Any]:
    """Safely parse JSON, attempting to extract JSON from mixed content."""
    if not text:
        return {}
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"(\{.*\}|\[.*\])", text, re.S)
        if match:
            return json.loads(match.group(1))
    return {}


def _sanitize_filename(name: str) -> str:
    """Sanitize filename by removing invalid characters."""
    name = re.sub(r'[\\/:*?"<>|]+', "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    return (name or "paper")[:120]


def _build_llm_strategy(
    provider: str,
    token: Optional[str],
    schema: Dict[str, Any],
    instruction: str,
    extra_headers: Optional[Dict[str, str]] = None,
) -> LLMExtractionStrategy:
    """Build LLM extraction strategy."""
    if provider != "ollama" and not token:
        raise ValueError(f"LLM provider {provider} requires api_token")
    extra_args = {"temperature": 0, "top_p": 0.9, "max_tokens": 2000}
    if extra_headers:
        extra_args["extra_headers"] = extra_headers

    return LLMExtractionStrategy(
        llm_config=LLMConfig(provider=provider, api_token=token),
        schema=schema,
        extraction_type="schema",
        instruction=instruction,
        extra_args=extra_args,
    )


def _build_search_js(keywords: List[str], subjects: List[str]) -> str:
    """Build JavaScript code for search interaction."""
    query = " ".join([k.strip() for k in keywords if k and k.strip()])
    return f"""
(async () => {{
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  const $x = (xpath) => document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
  const click = (xpath) => {{ const el = $x(xpath); if (el) el.click(); return !!el; }};
  const input = (xpath, value) => {{
      const el = $x(xpath);
      if (!el) return false;
      el.focus();
      el.value = '';
      el.dispatchEvent(new Event('input', {{bubbles:true}}));
      el.value = value;
      el.dispatchEvent(new Event('input', {{bubbles:true}}));
      return true;
  }};
  const clickByText = (text) => {{
      const nodes = Array.from(document.querySelectorAll('a,button,li,span,label,div'))
        .filter(el => el.textContent && el.textContent.trim() === text);
      if (nodes.length) {{ nodes[0].click(); return true; }}
      const nodes2 = Array.from(document.querySelectorAll('a,button,li,span,label,div'))
        .filter(el => el.textContent && el.textContent.includes(text));
      if (nodes2.length) {{ nodes2[0].click(); return true; }}
      return false;
  }};

  if ({json.dumps(query)}.length === 0) return;

  input({json.dumps(XPATH_SEARCH_INPUT)}, {json.dumps(query)});
  click({json.dumps(XPATH_SEARCH_BUTTON)});
  await sleep(1200);

  // Subject filter (best-effort)
  const subjects = {json.dumps(subjects)};
  if (subjects.length) {{
      click({json.dumps(XPATH_SUBJECT_FILTER)});
      await sleep(200);
      for (const s of subjects) {{
          clickByText(s);
          await sleep(200);
      }}
  }}

  // reduce DOM for LLM extraction
  const container = $x({json.dumps(XPATH_RESULTS)});
  if (container) {{
      document.body.innerHTML = container.outerHTML;
  }}
}})();
"""


def _wait_for_xpath(xpath: str) -> str:
    """Build JavaScript wait condition for XPath."""
    return f"""() => !!document.evaluate({json.dumps(xpath)}, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue"""


def _extract_pdf_link(html: str, base_url: str) -> Optional[str]:
    """Extract PDF link from HTML."""
    # Try XPath first
    try:
        from lxml import etree

        tree = etree.HTML(html)
        nodes = tree.xpath(XPATH_DOWNLOAD_BTN)
        if nodes:
            node = nodes[0]
            if hasattr(node, "get"):
                href = node.get("href") or node.get("data-href") or node.get("data-url")
                if href:
                    return urljoin(base_url, href)
                onclick = node.get("onclick") or ""
                m = re.search(r"(https?://[^'\"\\s]+\\.pdf)", onclick)
                if m:
                    return m.group(1)
    except Exception:
        pass

    # Fallback: search for pdf links
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if ".pdf" in href.lower():
            return urljoin(base_url, href)
    return None


def _choose_item(
    items: List[Dict[str, Any]], selected_index: int, selected_title: Optional[str]
) -> Optional[Dict[str, Any]]:
    """Choose an item from search results by index or title."""
    if selected_title:
        for it in items:
            if selected_title in (it.get("title") or ""):
                return it
    if 0 <= selected_index < len(items):
        return items[selected_index]
    return None


class CyberLeninkaService:
    """Service for interacting with CyberLeninka."""

    def __init__(self, headless: bool = True, base_url: str = BASE_URL):
        self.browser_config = BrowserConfig(headless=headless, java_script_enabled=True)
        self.base_url = base_url.rstrip("/")

    async def search(self, payload: CyberleninkaPayload) -> SearchResponse:
        """Search for papers using unified payload."""
        warnings = []
        keywords = payload.keyword
        subjects = payload.subjects

        js_code = _build_search_js(keywords, subjects)

        instruction = f"""
Extract up to {payload.max_results} papers from the search results list.
Return JSON with key "items".
Each item fields: title, authors, year, journal, subject, detail_link.
detail_link should be the URL to the paper detail page if present.
Return strictly valid JSON.
"""

        llm_strategy = _build_llm_strategy(
            provider=payload.effective_llm_provider,
            token=payload.effective_llm_api_token,
            schema=PaperList.model_json_schema(),
            instruction=instruction,
            extra_headers=payload.llm_extra_headers,
        )

        crawler_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            js_code=[js_code],
            wait_for=_wait_for_xpath(XPATH_RESULTS),
            page_timeout=payload.timeout_ms,
            word_count_threshold=1,
            extraction_strategy=llm_strategy,
        )

        async with AsyncWebCrawler(config=self.browser_config) as crawler:
            result = await crawler.arun(url=payload.base_url, config=crawler_config)

        if not result.success:
            return SearchResponse(
                success=False, warnings=[result.error_message or "crawl_failed"]
            )

        payload_data = _safe_json_loads(result.extracted_content)
        raw_items = payload_data.get("items", [])
        items: List[Dict[str, Any]] = []

        for idx, raw in enumerate(raw_items[: payload.max_results]):
            try:
                item = PaperItem.model_validate(raw)
                items.append({**item.model_dump(), "index": idx})
            except Exception as e:
                warnings.append(f"item_parse_error: {e}")

        return SearchResponse(
            success=True,
            items=items,
            warnings=warnings,
            raw_excerpt=(result.markdown[:1000] if result.markdown else None),
            total_count=len(items),
        )

    async def download(self, payload: CyberleninkaPayload) -> DownloadResponse:
        """Download a paper PDF using unified payload."""
        warnings = []
        detail_link = payload.detail_link

        # if detail_link not provided, re-search and pick item
        if not detail_link:
            search_payload = CyberleninkaPayload(
                action="search",
                base_url=payload.base_url,
                search_params=payload.search_params,
                llm_provider=payload.llm_provider,
                llm_api_token=payload.llm_api_token,
                llm_extra_headers=payload.llm_extra_headers,
                timeout_ms=payload.timeout_ms,
            )
            search_res = await self.search(search_payload)
            if not search_res.items:
                return DownloadResponse(success=False, warnings=["no_search_results"])

            chosen = _choose_item(
                search_res.items, payload.selected_index, payload.selected_title
            )
            if not chosen:
                return DownloadResponse(
                    success=False, warnings=["invalid_selected_index"]
                )
            detail_link = chosen.get("detail_link")

        if not detail_link:
            return DownloadResponse(success=False, warnings=["missing_detail_link"])

        crawler_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            wait_for=_wait_for_xpath(XPATH_DOWNLOAD_BTN),
            page_timeout=payload.timeout_ms,
        )

        async with AsyncWebCrawler(config=self.browser_config) as crawler:
            result = await crawler.arun(url=detail_link, config=crawler_config)

        pdf_url = _extract_pdf_link(result.cleaned_html, detail_link)
        if not pdf_url:
            return DownloadResponse(success=False, warnings=["pdf_not_found"])

        os.makedirs(payload.download_path, exist_ok=True)
        filename = (
            _sanitize_filename(
                payload.selected_title or os.path.basename(urlparse(pdf_url).path)
            )
            + ".pdf"
        )
        file_path = os.path.join(payload.download_path, filename)

        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                async with client.stream("GET", pdf_url) as resp:
                    with open(file_path, "wb") as f:
                        async for chunk in resp.aiter_bytes():
                            f.write(chunk)
        except Exception as e:
            return DownloadResponse(success=False, warnings=[f"download_failed: {e}"])

        return DownloadResponse(
            success=True, pdf_url=pdf_url, file_path=file_path, warnings=warnings
        )
