from __future__ import annotations

import asyncio
import concurrent.futures
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig

from src.domain.document_normalization import normalize_document_body



_HANS_DETAIL_SELECTORS = [
    "#ctl00_ContentPlaceHolder1_div_abs_zw",
    "#ctl00_ContentPlaceHolder1_div_abs_yw",
    ".articles_main",
    ".p_br",
]



def _clean_selector_text(text: str) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in str(text or "").splitlines()]
    return "\n\n".join(line for line in lines if line)



def _render_hans_detail_html(url: str) -> str:
    async def _run() -> str:
        async with AsyncWebCrawler(
            config=BrowserConfig(headless=True, java_script_enabled=True)
        ) as crawler:
            result = await crawler.arun(
                url=url,
                config=CrawlerRunConfig(cache_mode=CacheMode.BYPASS),
            )
        if not getattr(result, "success", False):
            return ""
        return str(getattr(result, "cleaned_html", "") or "")

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        try:
            return asyncio.run(_run())
        except Exception:
            return ""

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(lambda: asyncio.run(_run()))
        try:
            return future.result()
        except Exception:
            return ""



def fetch_detail_html(url: str) -> dict[str, Any]:
    target = str(url or "").strip()
    if not target:
        return {"success": False, "html": "", "warnings": ["html_fetch_missing_url"]}
    try:
        response = httpx.get(
            target,
            follow_redirects=True,
            timeout=60,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
        )
        response.raise_for_status()
        html = response.text
        final_url = str(response.url)
        warnings: list[str] = []
        if "www.hanspub.org/journal/paperinformation" in target:
            rendered_html = _render_hans_detail_html(target)
            if rendered_html:
                html = rendered_html
                final_url = target
                warnings.append("fallback:hans_rendered_html")
        return {
            "success": True,
            "html": html,
            "final_url": final_url,
            "warnings": warnings,
        }
    except Exception as exc:
        return {
            "success": False,
            "html": "",
            "warnings": [f"html_fetch_failed:{exc}"],
            "error": str(exc),
        }



def extract_readable_body(html: str) -> dict[str, Any]:
    normalized = normalize_document_body(html)
    if normalized.text:
        return {
            "success": True,
            "body": normalized.text,
            "body_selector": normalized.body_selector,
            "warnings": [],
        }

    soup = BeautifulSoup(html or "", "html.parser")
    for selector in _HANS_DETAIL_SELECTORS:
        node = soup.select_one(selector)
        if node is None:
            continue
        title_node = node.select_one("h1") or soup.select_one("h1")
        parts: list[str] = []
        if title_node is not None:
            title_text = _clean_selector_text(title_node.get_text(" ", strip=True))
            if title_text:
                parts.append(f"# {title_text}")
        body_text = _clean_selector_text(node.get_text("\n", strip=True))
        if body_text:
            parts.append(body_text)
        extracted = "\n\n".join(part for part in parts if part).strip()
        if extracted:
            return {
                "success": True,
                "body": extracted,
                "body_selector": selector,
                "warnings": ["fallback:selector_extract"],
            }

    return {
        "success": False,
        "body": "",
        "body_selector": normalized.body_selector,
        "warnings": [],
    }



def normalize_body_with_format_llm(body: str) -> str:
    normalized = normalize_document_body(body)
    return normalized.text or str(body or "").strip()



def validate_normalized_body(text: str, min_length: int = 200) -> bool:
    cleaned = str(text or "").strip()
    if len(cleaned) < min_length:
        return False
    boilerplate_tokens = ["登录", "注册", "首页", "搜索"]
    if all(token in cleaned for token in boilerplate_tokens):
        return False
    return True
