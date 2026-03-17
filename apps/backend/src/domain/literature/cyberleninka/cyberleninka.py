# src/domain/literature/cyberleninka.py
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Literal, Optional
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
from pydantic import BaseModel, Field, validator

log = logging.getLogger(__name__)

BASE_URL = "https://cyberleninka.ru/"

# ===== XPaths provided =====
XPATH_SEARCH_INPUT = '//*[@id="search-box-light"]/form/fieldset/input'
XPATH_SEARCH_BUTTON = '//*[@id="search-box-light"]/form/fieldset/button'
XPATH_SUBJECT_FILTER = '//*[@id="body"]/div[3]/div/div[1]/div[2]/div/div[2]/div'
XPATH_SUBJECT_LIST = '//*[@id="body"]/div[3]/div/div[1]/div[2]/div/div[2]/ul'
XPATH_RESULTS = '//*[@id="search-results"]'
XPATH_FIRST_TITLE = '//*[@id="search-results"]/li[1]/h2'
XPATH_DOWNLOAD_BTN = '//*[@id="btn-download"]'


# ===== Models =====
class SearchParams(BaseModel):
    keyword: List[str] = Field(..., min_length=1)
    filters: Dict[str, List[str]] = Field(default_factory=dict)
    limit: int = 20

    @validator("limit")
    def limit_range(cls, v):
        return max(1, min(v, 50))


class CyberleninkaPayload(BaseModel):
    action: Literal["search", "download"] = "search"
    base_url: str = BASE_URL

    search_params: SearchParams
    selected_index: int = 0
    selected_title: Optional[str] = None
    detail_link: Optional[str] = None

    download_path: str = "./downloads"
    llm_provider: str = "ollama"  # open-source first
    llm_api_token: Optional[str] = None
    llm_extra_headers: Optional[Dict[str, str]] = None
    timeout_ms: int = 80000


class PaperItem(BaseModel):
    title: str
    authors: Optional[str] = None
    year: Optional[str] = None
    journal: Optional[str] = None
    subject: Optional[str] = None
    detail_link: Optional[str] = None


class PaperList(BaseModel):
    items: List[PaperItem] = Field(default_factory=list)


class SearchResponse(BaseModel):
    success: bool
    items: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    raw_excerpt: Optional[str] = None


class DownloadResponse(BaseModel):
    success: bool
    pdf_url: Optional[str] = None
    file_path: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)


# ===== Helpers =====
def _safe_json_loads(text: str) -> Dict[str, Any]:
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
    name = re.sub(r'[\\/:*?"<>|]+', "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    return (name or "paper")[:120]


def _build_llm_strategy(
    provider: str,
    token: Optional[str],
    schema: Dict[str, Any],
    instruction: str,
    extra_headers: Optional[Dict[str, str]] = None,
):
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
    return f"""() => !!document.evaluate({json.dumps(xpath)}, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue"""


def _extract_pdf_link(html: str, base_url: str) -> Optional[str]:
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
):
    if selected_title:
        for it in items:
            if selected_title in (it.get("title") or ""):
                return it
    if 0 <= selected_index < len(items):
        return items[selected_index]
    return None


# ===== Service =====
class CyberLeninkaService:
    def __init__(self, headless: bool = True):
        self.browser_config = BrowserConfig(headless=headless, java_script_enabled=True)

    async def search(self, req: CyberleninkaPayload) -> SearchResponse:
        warnings = []
        keywords = req.search_params.keyword
        subjects = (
            req.search_params.filters.get("subject", [])
            if req.search_params.filters
            else []
        )

        js_code = _build_search_js(keywords, subjects)

        instruction = f"""
Extract up to {req.search_params.limit} papers from the search results list.
Return JSON with key "items".
Each item fields: title, authors, year, journal, subject, detail_link.
detail_link should be the URL to the paper detail page if present.
Return strictly valid JSON.
"""

        llm_strategy = _build_llm_strategy(
            provider=req.llm_provider,
            token=req.llm_api_token,
            schema=PaperList.model_json_schema(),
            instruction=instruction,
            extra_headers=req.llm_extra_headers,
        )

        crawler_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            js_code=[js_code],
            wait_for=_wait_for_xpath(XPATH_RESULTS),
            page_timeout=req.timeout_ms,
            word_count_threshold=1,
            extraction_strategy=llm_strategy,
        )

        async with AsyncWebCrawler(config=self.browser_config) as crawler:
            result = await crawler.arun(url=req.base_url, config=crawler_config)

        if not result.success:
            return SearchResponse(
                success=False, warnings=[result.error_message or "crawl_failed"]
            )

        payload = _safe_json_loads(result.extracted_content)
        raw_items = payload.get("items", [])
        items: List[Dict[str, Any]] = []

        for idx, raw in enumerate(raw_items[: req.search_params.limit]):
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
        )

    async def download(self, req: CyberleninkaPayload) -> DownloadResponse:
        warnings = []
        detail_link = req.detail_link

        # if detail_link not provided, re-search and pick item
        if not detail_link:
            search_res = await self.search(req)
            if not search_res.items:
                return DownloadResponse(success=False, warnings=["no_search_results"])
            chosen = _choose_item(
                search_res.items, req.selected_index, req.selected_title
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
            page_timeout=req.timeout_ms,
        )

        async with AsyncWebCrawler(config=self.browser_config) as crawler:
            result = await crawler.arun(url=detail_link, config=crawler_config)

        pdf_url = _extract_pdf_link(result.cleaned_html, detail_link)
        if not pdf_url:
            return DownloadResponse(success=False, warnings=["pdf_not_found"])

        os.makedirs(req.download_path, exist_ok=True)
        filename = (
            _sanitize_filename(
                req.selected_title or os.path.basename(urlparse(pdf_url).path)
            )
            + ".pdf"
        )
        file_path = os.path.join(req.download_path, filename)

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


# ===== Entry =====
async def cyberleninka_workflow(payload: Dict[str, Any]) -> Dict[str, Any]:
    req = CyberleninkaPayload.model_validate(payload)
    service = CyberLeninkaService()

    if req.action == "search":
        res = await service.search(req)
        return res.model_dump()

    if req.action == "download":
        res = await service.download(req)
        return res.model_dump()

    return {"success": False, "warnings": ["unknown_action"]}
