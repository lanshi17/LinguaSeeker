# src/domain/literature/pubscholar/service.py
"""PubScholar service implementation."""

import json
import logging
import os
import re
from html import unescape
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, quote_plus, urljoin, urlparse

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
    for meta in soup.find_all("meta"):
        name = (meta.get("name") or "").lower()
        if name == "citation_pdf_url":
            content = (meta.get("content") or "").strip()
            if content:
                links.append(urljoin(base_url, content))
    return list(dict.fromkeys(links))


class PubScholarService:
    """Service for interacting with PubScholar."""

    def __init__(self, headless: bool = True, base_url: str = BASE_URL):
        self.browser_config = BrowserConfig(headless=headless, java_script_enabled=True)
        self.base_url = base_url.rstrip("/")
        self._user_agent = "Mozilla/5.0"

    @staticmethod
    def _decode_duckduckgo_link(href: str) -> str:
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

    async def _duckduckgo_search(
        self, query: str, limit: int = 10
    ) -> List[Dict[str, str]]:
        if not query.strip():
            return []
        url = "https://html.duckduckgo.com/html/"
        headers = {
            "user-agent": self._user_agent,
            "accept": "text/html,application/xhtml+xml",
            "referer": f"https://duckduckgo.com/?q={quote_plus(query)}",
        }
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url, params={"q": query}, headers=headers)
            resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        results: List[Dict[str, str]] = []
        seen = set()
        for anchor in soup.select("a.result__a"):
            href = self._decode_duckduckgo_link(anchor.get("href") or "")
            if not href or href in seen:
                continue
            seen.add(href)
            title = anchor.get_text(" ", strip=True) or href
            results.append({"title": title, "url": href})
            if len(results) >= limit:
                break
        return results

    async def _search_via_duckduckgo(
        self, payload: PubScholarPayload
    ) -> List[PaperItem]:
        query = payload.keyword.strip()
        if not query:
            return []
        # Prefer pubscholar pages first, then relax to broader academic links.
        queries = [
            f"site:pubscholar.cn/literatures {query}",
            f"site:pubscholar.cn {query}",
            f"{query} 学术 论文",
        ]
        raw_hits: List[Dict[str, str]] = []
        for q in queries:
            try:
                hits = await self._duckduckgo_search(
                    q, limit=max(payload.max_results, 8)
                )
            except Exception:
                hits = []
            raw_hits.extend(hits)
            if len(raw_hits) >= payload.max_results:
                break

        dedup: List[PaperItem] = []
        seen = set()
        subjects = payload.search_params.filters.get("subject", [])
        for hit in raw_hits:
            link = hit.get("url") or ""
            if not link or link in seen:
                continue
            seen.add(link)
            try:
                dedup.append(
                    PaperItem(
                        title=hit.get("title") or link,
                        source_link=link,
                        has_full_text=(
                            True
                            if re.search(r"\.pdf(?:$|[?#])", link, re.IGNORECASE)
                            else None
                        ),
                        subjects=subjects if isinstance(subjects, list) else None,
                    )
                )
            except Exception:
                continue
            if len(dedup) >= payload.max_results:
                break
        return dedup

    async def _download_from_candidates(
        self,
        candidates: List[str],
        payload: PubScholarPayload,
    ) -> tuple[Optional[str], Optional[str], List[str]]:
        warnings: List[str] = []
        queue = [c for c in candidates if c]
        visited = set()
        os.makedirs(payload.download_path, exist_ok=True)
        title = payload.selected_title or payload.keyword or "paper"
        filename = _sanitize_filename(title) + ".pdf"
        file_path = os.path.join(payload.download_path, filename)

        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue
                visited.add(current)
                try:
                    resp = await client.get(
                        current,
                        headers={"user-agent": self._user_agent, "accept": "*/*"},
                    )
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
                        extra = _extract_pdf_links_by_html(
                            resp.text or "", str(resp.url)
                        )
                        for link in extra:
                            if link not in visited:
                                queue.append(link)
                except Exception as exc:
                    warnings.append(f"download_probe_failed:{current}:{exc}")
        return None, None, warnings

    async def search(self, payload: PubScholarPayload) -> SearchResponse:
        """Search for papers using unified payload."""
        warnings = []
        fallback_items = await self._search_via_duckduckgo(payload)
        if fallback_items:
            warnings.append("fallback_search:duckduckgo")
            return SearchResponse(
                success=True,
                items=fallback_items[: payload.max_results],
                warnings=warnings,
                raw_excerpt=None,
                total_count=min(len(fallback_items), payload.max_results),
            )

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
        items: List[PaperItem] = []
        raw_excerpt: Optional[str] = None

        try:
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

            if result.success:
                payload_data = _safe_json_loads(result.extracted_content)
                extracted_items: List[Dict[str, Any]] = []
                if isinstance(payload_data, list):
                    extracted_items = [
                        item for item in payload_data if isinstance(item, dict)
                    ]
                elif isinstance(payload_data, dict):
                    raw_items = payload_data.get("items", [])
                    if isinstance(raw_items, list):
                        extracted_items = [
                            item for item in raw_items if isinstance(item, dict)
                        ]

                for raw in extracted_items[: payload.max_results]:
                    try:
                        items.append(PaperItem.model_validate(raw))
                    except Exception as e:
                        warnings.append(f"item_parse_error: {e}")

                if result.markdown:
                    raw_excerpt = result.markdown.fit_markdown[:1000]
            else:
                warnings.append(result.error_message or "crawl_failed")
        except Exception as exc:
            warnings.append(f"crawl_failed:{exc}")

        return SearchResponse(
            success=bool(items),
            items=items,
            warnings=warnings,
            raw_excerpt=raw_excerpt,
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

        pdf_links: List[str] = []
        if ".pdf" in source_link.lower():
            pdf_links.append(source_link)

        # 2) Direct HTTP parse first (no browser dependency)
        if not pdf_links:
            try:
                async with httpx.AsyncClient(
                    timeout=30, follow_redirects=True
                ) as client:
                    page = await client.get(
                        source_link,
                        headers={
                            "user-agent": self._user_agent,
                            "accept": "text/html,application/xhtml+xml",
                        },
                    )
                    if page.status_code < 400:
                        pdf_links.extend(
                            _extract_pdf_links_by_html(page.text, str(page.url))
                        )
            except Exception as exc:
                warnings.append(f"http_parse_failed:{exc}")

        # 3) Browser+LLM fallback if needed
        if not pdf_links:
            try:
                async with AsyncWebCrawler(config=self.browser_config) as crawler:
                    result = await crawler.arun(
                        url=source_link,
                        config=CrawlerRunConfig(cache_mode=CacheMode.BYPASS),
                    )
                    if result.success:
                        pdf_links.extend(
                            _extract_pdf_links_by_html(result.cleaned_html, source_link)
                        )
            except Exception as exc:
                warnings.append(f"crawl_parse_failed:{exc}")

        # 4) Generic PDF search fallback for hard anti-bot pages
        if not pdf_links:
            query = payload.selected_title or payload.keyword
            try:
                hits = await self._duckduckgo_search(f"{query} filetype:pdf", limit=10)
                for hit in hits:
                    url = hit.get("url") or ""
                    if re.search(r"\.pdf(?:$|[?#])", url, re.IGNORECASE):
                        pdf_links.append(url)
            except Exception as exc:
                warnings.append(f"pdf_search_failed:{exc}")
            if pdf_links:
                warnings.append("fallback_pdf:duckduckgo")

        if not pdf_links:
            return DownloadResponse(
                success=False, warnings=warnings + ["pdf_not_found"]
            )

        file_path, final_pdf_url, dl_warnings = await self._download_from_candidates(
            pdf_links, payload
        )
        warnings.extend(dl_warnings)
        if not file_path:
            return DownloadResponse(
                success=False, warnings=warnings + ["download_failed"]
            )

        return DownloadResponse(
            success=True,
            pdf_url=final_pdf_url,
            file_path=file_path,
            warnings=warnings,
        )
