from __future__ import annotations

import asyncio
from types import SimpleNamespace

import src.domain.literature.firecrawl_service as firecrawl_service


def test_firecrawl_service_scrape_markdown_uses_crawl4ai_without_firecrawl_api_key(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeCrawler:
        def __init__(self, config: object = None) -> None:
            captured["browser_config"] = config

        async def __aenter__(self) -> "FakeCrawler":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def arun(self, *, url: str, config: object) -> object:
            captured["url"] = url
            captured["run_config"] = config
            return SimpleNamespace(
                success=True,
                markdown=SimpleNamespace(fit_markdown="# Example\n\ncontent"),
                cleaned_html="<html><title>Example title</title></html>",
                metadata={"title": "Example title", "url": "https://example.org/final"},
            )

    monkeypatch.setattr(firecrawl_service, "AsyncWebCrawler", FakeCrawler)

    service = firecrawl_service.FirecrawlService()
    result = asyncio.run(service.scrape_markdown("https://example.org/source"))

    assert captured["url"] == "https://example.org/source"
    assert result.source_url == "https://example.org/source"
    assert result.final_url == "https://example.org/final"
    assert result.title == "Example title"
    assert result.markdown == "# Example\n\ncontent"
    assert result.metadata["provider"] == "crawl4ai"
