from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import httpx


@dataclass(frozen=True)
class FirecrawlMarkdownResult:
    source_url: str
    final_url: str
    title: str
    markdown: str
    metadata: Dict[str, Any] = field(default_factory=dict)


def _strip_html_to_markdown(content: str) -> str:
    if not content:
        return ""
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", content)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|div|section|article|li|h1|h2|h3|h4|h5|h6)>", "\n\n", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\r", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def _extract_title(html_text: str, fallback_url: str) -> str:
    if html_text:
        match = re.search(r"(?is)<title[^>]*>(.*?)</title>", html_text)
        if match:
            title = html.unescape(match.group(1)).strip()
            if title:
                return title
    parsed = urlparse(fallback_url)
    return parsed.netloc or fallback_url


class FirecrawlService:
    def __init__(self, timeout: float = 25.0) -> None:
        self._timeout = timeout

    async def scrape_markdown(self, url: str) -> FirecrawlMarkdownResult:
        normalized_url = str(url or "").strip()
        if not normalized_url:
            raise ValueError("url is required")

        async with httpx.AsyncClient(
            timeout=self._timeout, follow_redirects=True
        ) as client:
            response = await client.get(normalized_url)
            response.raise_for_status()
            body = response.text
            final_url = str(response.url)
            content_type = str(response.headers.get("content-type") or "")

        markdown = _strip_html_to_markdown(body)
        title = _extract_title(body, final_url)
        return FirecrawlMarkdownResult(
            source_url=normalized_url,
            final_url=final_url,
            title=title,
            markdown=markdown,
            metadata={"provider": "httpx", "content_type": content_type},
        )


_firecrawl_service: Optional[FirecrawlService] = None


def get_firecrawl_service() -> FirecrawlService:
    global _firecrawl_service
    if _firecrawl_service is None:
        _firecrawl_service = FirecrawlService()
    return _firecrawl_service
