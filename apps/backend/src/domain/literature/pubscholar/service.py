# src/domain/literature/pubscholar/service.py
"""PubScholar service implementation."""

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
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

try:
    from .locators import (
        XPATH_FULLTEXT_BTN,
        XPATH_LANGUAGE_HEADER,
        XPATH_PAPER_TYPE_HEADER,
        XPATH_RESULTS_CONTAINER,
        XPATH_SEARCH_BUTTON,
        XPATH_SEARCH_INPUT,
    )
    from .models import (
        BASE_URL,
        DownloadRequest,
        DownloadResponse,
        PaperItem,
        PaperList,
        PubScholarPayload,
        SearchFilters,
        SearchRequest,
        SearchResponse,
    )
except ImportError:
    from locators import (
        XPATH_FULLTEXT_BTN,
        XPATH_LANGUAGE_HEADER,
        XPATH_PAPER_TYPE_HEADER,
        XPATH_RESULTS_CONTAINER,
        XPATH_SEARCH_BUTTON,
        XPATH_SEARCH_INPUT,
    )
    from models import (
        BASE_URL,
        DownloadRequest,
        DownloadResponse,
        PaperItem,
        PaperList,
        PubScholarPayload,
        SearchFilters,
        SearchRequest,
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


def _build_search_js(
    keyword: str,
    language: Optional[str],
    paper_types: List[str],
    full_text_only: bool,
) -> str:
    """Build JavaScript code for search interaction."""
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
      const candidates = Array.from(document.querySelectorAll('button,span,li,div,a'))
        .filter(el => el.textContent && el.textContent.trim() === text);
      if (candidates.length) {{ candidates[0].click(); return true; }}
      return false;
  }};

  input({json.dumps(XPATH_SEARCH_INPUT)}, {json.dumps(keyword)});
  click({json.dumps(XPATH_SEARCH_BUTTON)});
  await sleep(1200);

  // 语种
  if ({json.dumps(language)}) {{
      click({json.dumps(XPATH_LANGUAGE_HEADER)});
      await sleep(200);
      clickByText({json.dumps(language)});
      await sleep(300);
  }}

  // 论文类型
  const types = {json.dumps(paper_types)};
  if (types.length) {{
      click({json.dumps(XPATH_PAPER_TYPE_HEADER)});
      await sleep(200);
      for (const t of types) {{
          clickByText(t);
          await sleep(200);
      }}
  }}

  // 可获取全文
  if ({json.dumps(full_text_only)}) {{
      click({json.dumps(XPATH_FULLTEXT_BTN)});
      await sleep(200);
  }}

  // 只保留结果容器，减少 LLM token
  const container = $x({json.dumps(XPATH_RESULTS_CONTAINER)});
  if (container) {{
      document.body.innerHTML = container.outerHTML;
  }}
}})();
"""


def _wait_for_results_js() -> str:
    """Build JavaScript wait condition for results."""
    return f"""() => !!document.evaluate({json.dumps(XPATH_RESULTS_CONTAINER)}, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue"""


def _extract_pdf_links_by_html(html: str, base_url: str) -> List[str]:
    """Extract PDF links from HTML using BeautifulSoup."""
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if ".pdf" in href.lower():
            links.append(urljoin(base_url, href))
    return list(dict.fromkeys(links))


class PubScholarService:
    """Service for interacting with PubScholar."""

    def __init__(self, headless: bool = True, base_url: str = BASE_URL):
        self.browser_config = BrowserConfig(headless=headless, java_script_enabled=True)
        self.base_url = base_url.rstrip("/")

    async def search(self, payload: PubScholarPayload) -> SearchResponse:
        """Search for papers using unified payload."""
        warnings = []
        internal_filters = payload.to_search_filters()

        js_code = _build_search_js(
            payload.keyword,
            internal_filters.language.value if internal_filters.language else None,
            [pt.value for pt in internal_filters.paper_types],
            internal_filters.full_text_only,
        )

        instruction = f"""
You are given a search result list of academic papers.
Extract at most {payload.max_results} items into JSON following the schema.
Fields: title, authors, year, journal, paper_type, language, has_full_text, source_link (journal official page), subjects.
If missing, use null. Return strictly valid JSON.
"""

        llm_strategy = _build_llm_strategy(
            provider=payload.llm_provider,
            token=payload.llm_api_token,
            schema=PaperList.model_json_schema(),
            instruction=instruction,
            extra_headers=payload.llm_extra_headers,
        )

        crawler_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            js_code=[js_code],
            wait_for=_wait_for_results_js(),
            page_timeout=payload.timeout_ms,
            word_count_threshold=1,
            extraction_strategy=llm_strategy,
            markdown_generator=DefaultMarkdownGenerator(
                content_filter=PruningContentFilter(
                    threshold=0.5, threshold_type="fixed", min_word_threshold=0
                ),
                options={"ignore_links": False},
            ),
        )

        async with AsyncWebCrawler(config=self.browser_config) as crawler:
            result = await crawler.arun(url=payload.base_url, config=crawler_config)

        if not result.success:
            return SearchResponse(
                success=False, warnings=[result.error_message or "crawl_failed"]
            )

        payload_data = _safe_json_loads(result.extracted_content)
        items = []
        for raw in payload_data.get("items", [])[: payload.max_results]:
            try:
                items.append(PaperItem.model_validate(raw))
            except Exception as e:
                warnings.append(f"item_parse_error: {e}")

        return SearchResponse(
            success=True,
            items=items,
            warnings=warnings,
            raw_excerpt=(
                result.markdown.fit_markdown[:1000] if result.markdown else None
            ),
            total_count=len(items),
        )

    async def download(self, payload: PubScholarPayload) -> DownloadResponse:
        """Download a paper PDF using unified payload."""
        warnings = []

        # 1) Get source_link
        source_link = payload.detail_link
        if not source_link:
            # Search for the paper to get source_link
            search_payload = PubScholarPayload(
                action="search",
                base_url=payload.base_url,
                search_params=payload.search_params,
                selected_index=payload.selected_index,
                llm_provider=payload.llm_provider,
                llm_api_token=payload.llm_api_token,
                llm_extra_headers=payload.llm_extra_headers,
                timeout_ms=payload.timeout_ms,
            )
            search_res = await self.search(search_payload)
            if not search_res.items:
                return DownloadResponse(success=False, warnings=["no_search_results"])

            if payload.selected_index >= len(search_res.items):
                return DownloadResponse(
                    success=False,
                    warnings=[
                        f"selected_index_out_of_range: {payload.selected_index} >= {len(search_res.items)}"
                    ],
                )

            source_link = search_res.items[payload.selected_index].source_link

        if not source_link:
            return DownloadResponse(success=False, warnings=["missing_source_link"])

        # 2) Try to find PDF by rules first
        async with AsyncWebCrawler(config=self.browser_config) as crawler:
            base_url = source_link
            result = await crawler.arun(
                url=source_link, config=CrawlerRunConfig(cache_mode=CacheMode.BYPASS)
            )
            pdf_links = _extract_pdf_links_by_html(result.cleaned_html, base_url)

        # 3) If rules fail, use LLM fallback
        if not pdf_links:
            instruction = """
Extract all PDF URLs from the given page.
Return JSON with key pdf_urls (array of URLs).
If a URL is relative, convert it to absolute based on the page URL.
"""
            llm_strategy = _build_llm_strategy(
                provider=payload.llm_provider,
                token=payload.llm_api_token,
                schema={
                    "type": "object",
                    "properties": {
                        "pdf_urls": {"type": "array", "items": {"type": "string"}}
                    },
                },
                instruction=instruction,
                extra_headers=payload.llm_extra_headers,
            )
            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                llm_res = await crawler.arun(
                    url=source_link,
                    config=CrawlerRunConfig(
                        cache_mode=CacheMode.BYPASS, extraction_strategy=llm_strategy
                    ),
                )
            payload_data = _safe_json_loads(llm_res.extracted_content)
            pdf_links = payload_data.get("pdf_urls", [])

        if not pdf_links:
            return DownloadResponse(success=False, warnings=["pdf_not_found"])

        # 4) Download PDF
        pdf_url = pdf_links[0]
        os.makedirs(payload.download_path, exist_ok=True)
        title = payload.selected_title or payload.keyword or "paper"
        filename = _sanitize_filename(title) + ".pdf"
        file_path = os.path.join(payload.download_path, filename)

        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                async with client.stream("GET", pdf_url) as resp:
                    ctype = resp.headers.get("content-type", "").lower()
                    if "pdf" not in ctype:
                        warnings.append(f"non_pdf_content_type: {ctype}")
                    with open(file_path, "wb") as f:
                        async for chunk in resp.aiter_bytes():
                            f.write(chunk)
        except Exception as e:
            return DownloadResponse(success=False, warnings=[f"download_failed: {e}"])

        return DownloadResponse(
            success=True, pdf_url=pdf_url, file_path=file_path, warnings=warnings
        )
