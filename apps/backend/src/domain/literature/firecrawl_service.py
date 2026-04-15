from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, cast

from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig

from src.domain.document_normalization import normalize_document_body


@dataclass(frozen=True)
class FirecrawlMarkdownResult:
    source_url: str
    final_url: str
    title: str
    markdown: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class FirecrawlService:
    def __init__(
        self,
        *,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout_seconds: int = 60,
    ) -> None:
        self._browser_config = BrowserConfig(headless=True, java_script_enabled=True)
        self._timeout_seconds = timeout_seconds

    async def scrape_markdown(self, url: str) -> FirecrawlMarkdownResult:
        normalized_url = str(url or "").strip()
        if not normalized_url:
            raise ValueError("INPUT_INVALID: url is required")

        async with AsyncWebCrawler(config=self._browser_config) as crawler:
            result = cast(
                Any,
                await crawler.arun(
                    url=normalized_url,
                    config=CrawlerRunConfig(cache_mode=CacheMode.BYPASS),
                ),
            )

        if not result.success:
            raise RuntimeError(result.error_message or "Fetch no result from crawl4ai")

        markdown_obj = getattr(result, "markdown", None)
        raw_markdown = str(getattr(markdown_obj, "fit_markdown", "") or "").strip()
        fallback_html = str(getattr(result, "cleaned_html", "") or "").strip()
        normalized = normalize_document_body(raw_markdown or fallback_html)
        if not normalized.text:
            raise RuntimeError("Fetch no result from crawl4ai")

        metadata = getattr(result, "metadata", None)
        if not isinstance(metadata, dict):
            metadata = {}

        final_url = str(metadata.get("url") or normalized_url)
        title = str(metadata.get("title") or "").strip()
        if not title:
            cleaned_html = str(getattr(result, "cleaned_html", "") or "")
            if cleaned_html:
                soup = BeautifulSoup(cleaned_html, "html.parser")
                title = (soup.title.string or "").strip() if soup.title else ""
        if not title:
            title = final_url

        merged_metadata = {
            **metadata,
            "provider": "crawl4ai",
            "source_url": normalized_url,
            "normalized_body": True,
            "body_selector": normalized.body_selector,
        }
        return FirecrawlMarkdownResult(
            source_url=normalized_url,
            final_url=final_url,
            title=title,
            markdown=normalized.text,
            metadata=merged_metadata,
        )


_firecrawl_service: Optional[FirecrawlService] = None


def get_firecrawl_service() -> FirecrawlService:
    global _firecrawl_service
    if _firecrawl_service is None:
        _firecrawl_service = FirecrawlService()
    return _firecrawl_service
