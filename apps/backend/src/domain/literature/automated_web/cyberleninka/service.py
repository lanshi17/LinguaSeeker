# src/domain/literature/cyberleninka/service.py
"""CyberLeninka service implementation."""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, urljoin, urlparse

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


def _safe_json_loads(text: str) -> Any:
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
    for meta in soup.find_all("meta"):
        name = (meta.get("name") or "").lower()
        if name == "citation_pdf_url":
            content = (meta.get("content") or "").strip()
            if content:
                return urljoin(base_url, content)
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
        self.search_api_url = f"{self.base_url}/api/search"

    @staticmethod
    def _strip_tags(value: str) -> str:
        if not value:
            return ""
        return re.sub(r"<[^>]+>", "", value).strip()

    async def _search_via_public_api(
        self, payload: CyberleninkaPayload
    ) -> SearchResponse:
        warnings: List[str] = []
        query = " ".join([k.strip() for k in payload.keyword if k and k.strip()])
        if not query:
            return SearchResponse(success=False, warnings=["empty_query"])

        request_payload: Dict[str, Any] = {
            "mode": "articles",
            "q": query,
            "size": min(payload.max_results, 50),
            "from": 0,
        }
        if payload.subjects:
            request_payload["catalogs"] = payload.subjects

        headers = {
            "user-agent": "Mozilla/5.0",
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json",
            "referer": f"{self.base_url}/search?q={quote_plus(query)}",
        }

        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.post(
                    self.search_api_url, json=request_payload, headers=headers
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            return SearchResponse(success=False, warnings=[f"api_search_failed:{exc}"])

        raw_items = data.get("articles") if isinstance(data, dict) else []
        if not isinstance(raw_items, list):
            raw_items = []
        items: List[Dict[str, Any]] = []
        for idx, raw in enumerate(raw_items[: payload.max_results]):
            if not isinstance(raw, dict):
                continue
            title = self._strip_tags(str(raw.get("name") or "")) or "Untitled"
            authors_raw = raw.get("authors")
            authors = None
            if isinstance(authors_raw, list):
                authors = ", ".join([str(a) for a in authors_raw if a])
            elif isinstance(authors_raw, str):
                authors = authors_raw
            detail_link = raw.get("link")
            if detail_link:
                detail_link = urljoin(self.base_url + "/", str(detail_link))
            catalogs_value = raw.get("catalogs")
            subject_value: Optional[str]
            if isinstance(catalogs_value, list):
                subject_parts: List[str] = []
                for entry in catalogs_value:
                    if isinstance(entry, dict):
                        candidate = (
                            entry.get("name")
                            or entry.get("title")
                            or entry.get("label")
                            or entry.get("value")
                        )
                        if candidate:
                            subject_parts.append(str(candidate))
                    elif entry:
                        subject_parts.append(str(entry))
                subject_value = ", ".join(subject_parts) if subject_parts else None
            elif catalogs_value:
                subject_value = str(catalogs_value)
            else:
                subject_value = None
            item: Dict[str, Any] = {
                "title": title,
                "authors": authors,
                "year": str(raw.get("year")) if raw.get("year") else None,
                "journal": raw.get("journal"),
                "subject": subject_value,
                "detail_link": detail_link,
                "index": idx,
            }
            try:
                validated = PaperItem.model_validate(item)
                items.append({**validated.model_dump(), "index": idx})
            except Exception as exc:
                warnings.append(f"item_parse_error:{exc}")

        return SearchResponse(
            success=bool(items),
            items=items,
            warnings=warnings,
            raw_excerpt=None,
            total_count=len(items),
        )

    async def _search_via_crawler(self, payload: CyberleninkaPayload) -> SearchResponse:
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
        raw_items: List[Dict[str, Any]] = []
        if isinstance(payload_data, list):
            raw_items = [item for item in payload_data if isinstance(item, dict)]
        elif isinstance(payload_data, dict):
            items_value = payload_data.get("items", [])
            if isinstance(items_value, list):
                raw_items = [item for item in items_value if isinstance(item, dict)]
        items: List[Dict[str, Any]] = []

        for idx, raw in enumerate(raw_items[: payload.max_results]):
            try:
                item = PaperItem.model_validate(raw)
                items.append({**item.model_dump(), "index": idx})
            except Exception as e:
                warnings.append(f"item_parse_error: {e}")

        return SearchResponse(
            success=bool(items),
            items=items,
            warnings=warnings,
            raw_excerpt=(result.markdown[:1000] if result.markdown else None),
            total_count=len(items),
        )

    async def _fetch_detail_html(self, detail_link: str, timeout_ms: int) -> str:
        headers = {
            "user-agent": "Mozilla/5.0",
            "accept": "text/html,application/xhtml+xml",
            "referer": self.base_url,
        }
        async with httpx.AsyncClient(
            timeout=max(30, int(timeout_ms / 1000)), follow_redirects=True
        ) as client:
            resp = await client.get(detail_link, headers=headers)
            resp.raise_for_status()
            return resp.text

    async def search(self, payload: CyberleninkaPayload) -> SearchResponse:
        """Search for papers using unified payload."""
        api_result = await self._search_via_public_api(payload)
        if api_result.success and api_result.items:
            return api_result

        crawler_result = await self._search_via_crawler(payload)
        if api_result.warnings:
            crawler_result.warnings = api_result.warnings + crawler_result.warnings
        return crawler_result

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
        pdf_url: Optional[str] = None
        detail_html = ""
        try:
            detail_html = await self._fetch_detail_html(detail_link, payload.timeout_ms)
            pdf_url = _extract_pdf_link(detail_html, detail_link)
        except Exception as exc:
            warnings.append(f"detail_fetch_failed:{exc}")

        if not pdf_url:
            detail_clean = detail_link.rstrip("/")
            pdf_candidate = f"{detail_clean}/pdf"
            try:
                async with httpx.AsyncClient(
                    timeout=30, follow_redirects=True
                ) as client:
                    probe = await client.get(pdf_candidate)
                    if probe.status_code < 400 and probe.content.startswith(b"%PDF"):
                        pdf_url = str(probe.url)
            except Exception:
                pass

        if not pdf_url:
            return DownloadResponse(
                success=False, warnings=warnings + ["pdf_not_found"]
            )

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
                    resp.raise_for_status()
                    stream = resp.aiter_bytes()
                    first_chunk = await anext(stream, b"")
                    if not first_chunk:
                        return DownloadResponse(
                            success=False,
                            pdf_url=pdf_url,
                            warnings=warnings + ["download_empty"],
                        )
                    if not first_chunk.startswith(b"%PDF"):
                        return DownloadResponse(
                            success=False,
                            pdf_url=pdf_url,
                            warnings=warnings + ["download_not_pdf"],
                        )
                    with open(file_path, "wb") as f:
                        f.write(first_chunk)
                        async for chunk in stream:
                            f.write(chunk)
        except Exception as e:
            return DownloadResponse(
                success=False, warnings=warnings + [f"download_failed: {e}"]
            )

        return DownloadResponse(
            success=True, pdf_url=pdf_url, file_path=file_path, warnings=warnings
        )
