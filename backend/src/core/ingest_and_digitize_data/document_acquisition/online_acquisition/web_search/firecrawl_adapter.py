"""Firecrawl-based web search adapter."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from loguru import logger

from .adapter import SearchLink, WebSearchAdapter, WebSearchResult

# Regex patterns for extracting PDF links from scraped markdown/HTML
_PDF_URL_PATTERN = re.compile(
    r'https?://[^\s"\'<>]+\.pdf(?:[^\s"\'<>]*)',
    re.IGNORECASE,
)
_PDF_LINK_PATTERN = re.compile(
    r'\[([^\]]*)\]\((https?://[^\s"\'<>)]+\.pdf[^\s"\'<>)]*)\)',
    re.IGNORECASE,
)
_HREF_PDF_PATTERN = re.compile(
    r'href=["\']?(https?://[^\s"\'<>"\']+\.pdf[^\s"\'<>"\']*)',
    re.IGNORECASE,
)


def _to_dict(result: Any) -> Dict[str, Any]:
    """Convert SDK response to dict — handles both dict and Pydantic model returns."""
    if isinstance(result, dict):
        return result
    if hasattr(result, "model_dump"):
        return result.model_dump()
    if hasattr(result, "dict"):
        return result.dict()
    return {}


class FirecrawlAdapter(WebSearchAdapter):
    """Web search adapter using Firecrawl's search + scrape APIs.

    Environment:
        ``WEB_SEARCH_API_KEY`` — Firecrawl API key (``fc-...``).
        ``WEB_SEARCH_BASE_URL`` — optional, defaults to ``https://api.firecrawl.dev``.
    """

    def __init__(self, *, api_key: str, base_url: str = "", timeout: int = 30, max_results: int = 10) -> None:
        super().__init__(api_key=api_key, base_url=base_url, timeout=timeout, max_results=max_results)
        self._client = None  # lazy-init

    def _get_client(self):
        """Lazy-init the AsyncFirecrawl client."""
        if self._client is None:
            from firecrawl import AsyncFirecrawl

            kwargs = {"api_key": self.api_key}
            if self.base_url and self.base_url != "https://api.firecrawl.dev":
                kwargs["api_url"] = self.base_url
            self._client = AsyncFirecrawl(**kwargs)
        return self._client

    async def search(self, query: str, *, language: Optional[str] = None) -> WebSearchResult:
        """Search via Firecrawl and return candidate links."""
        warnings: list[str] = []
        all_links: list[SearchLink] = []

        try:
            client = self._get_client()
            raw_result = await client.search(query, limit=self.max_results)
            result = _to_dict(raw_result)

            web_results = result.get("web", [])
            for item in web_results:
                if isinstance(item, dict):
                    url = item.get("url", "")
                    title = item.get("title", "")
                elif hasattr(item, "url"):
                    url = getattr(item, "url", "")
                    title = getattr(item, "title", "")
                else:
                    continue

                if not url:
                    continue
                all_links.append(SearchLink(url=url, source="firecrawl-search", title=title or None))

        except Exception as exc:
            msg = f"firecrawl search failed: {exc}"
            logger.warning(msg)
            warnings.append(msg)

        return WebSearchResult(
            links=all_links,
            query=query,
            provider="firecrawl",
            warnings=warnings,
        )

    async def scrape_links(self, url: str) -> List[SearchLink]:
        """Scrape a page for PDF download links using Firecrawl."""
        links: list[SearchLink] = []
        try:
            client = self._get_client()
            raw_result = await client.scrape(url, formats=["markdown"])
            result = _to_dict(raw_result)

            markdown = result.get("markdown", "")
            if not markdown:
                return links

            # Extract PDF URLs from markdown content
            seen: set[str] = set()

            # Match markdown links to PDFs
            for match in _PDF_LINK_PATTERN.finditer(markdown):
                pdf_url = match.group(2)
                if pdf_url not in seen:
                    seen.add(pdf_url)
                    links.append(SearchLink(url=pdf_url, source="firecrawl-scrape"))

            # Match href attributes to PDFs
            for match in _HREF_PDF_PATTERN.finditer(markdown):
                pdf_url = match.group(1)
                if pdf_url not in seen:
                    seen.add(pdf_url)
                    links.append(SearchLink(url=pdf_url, source="firecrawl-scrape"))

            # Fallback: bare PDF URLs
            for match in _PDF_URL_PATTERN.finditer(markdown):
                pdf_url = match.group(0)
                if pdf_url not in seen:
                    seen.add(pdf_url)
                    links.append(SearchLink(url=pdf_url, source="firecrawl-scrape"))

        except Exception as exc:
            logger.warning("firecrawl scrape failed for {}: {}", url, exc)

        return links
