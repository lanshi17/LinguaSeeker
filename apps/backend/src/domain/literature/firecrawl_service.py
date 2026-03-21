from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import httpx

from src.config import settings


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
        self._base_url = (
            base_url or settings.firecrawl_base_url or "https://api.firecrawl.dev"
        ).rstrip("/")
        self._api_key = (api_key or settings.firecrawl_api_key or "").strip()
        self._timeout_seconds = timeout_seconds

    async def scrape_markdown(self, url: str) -> FirecrawlMarkdownResult:
        normalized_url = str(url or "").strip()
        if not normalized_url:
            raise ValueError("INPUT_INVALID: url is required")
        if not self._api_key:
            raise RuntimeError("INPUT_INVALID: firecrawl_api_key is not configured")

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "url": normalized_url,
            "formats": ["markdown"],
            "onlyMainContent": True,
        }

        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            response = await client.post(
                f"{self._base_url}/v1/scrape",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            body = response.json()

        if isinstance(body, dict) and body.get("success") is False:
            raise RuntimeError(str(body.get("error") or "Fetch no result from Firecrawl"))

        data = body.get("data", body) if isinstance(body, dict) else {}
        if not isinstance(data, dict):
            raise RuntimeError("Fetch no result from Firecrawl")

        metadata = data.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}

        markdown = str(data.get("markdown") or data.get("content") or "").strip()
        if not markdown:
            raise RuntimeError("Fetch no result from Firecrawl")

        title = str(data.get("title") or metadata.get("title") or normalized_url)
        final_url = str(
            data.get("finalUrl")
            or data.get("final_url")
            or metadata.get("finalUrl")
            or metadata.get("url")
            or normalized_url
        )
        merged_metadata = {**metadata, "provider": "firecrawl", "source_url": normalized_url}
        return FirecrawlMarkdownResult(
            source_url=normalized_url,
            final_url=final_url,
            title=title,
            markdown=markdown,
            metadata=merged_metadata,
        )


_firecrawl_service: Optional[FirecrawlService] = None


def get_firecrawl_service() -> FirecrawlService:
    global _firecrawl_service
    if _firecrawl_service is None:
        _firecrawl_service = FirecrawlService()
    return _firecrawl_service
