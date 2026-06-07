# Web Search

> Pluggable web search adapter for literature discovery. Provides an abstract interface over search engines (Firecrawl, etc.) to find candidate PDF download links from queries or page URLs.

## Quick Start

```python
from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.web_search import (
    FirecrawlAdapter,
)

adapter = FirecrawlAdapter(api_key="fc-...", max_results=10)

# Search for candidate links by query
result = await adapter.search("BRCA1 pathogenic variant ACMG guidelines")
for link in result.links:
    print(link.url, link.title, link.doi)

# Scrape a specific page for PDF links
links = await adapter.scrape_links("https://example.com/article-page")
```

## Architecture

```
WebSearchAdapter (abstract base)
    │
    ├── search(query) → WebSearchResult
    │       Discover candidate download links from a search query
    │
    └── scrape_links(url) → list[SearchLink]
            Extract PDF/metadata links from a specific page

FirecrawlAdapter (concrete implementation)
    ├── search()     → Firecrawl Search API
    └── scrape_links() → Firecrawl JSON scrape → markdown fallback
```

The adapter pattern allows swapping search backends without changing downstream orchestration. The gateway (`online_acquisition/gateway.py`) consumes `WebSearchAdapter` and does not know which provider is active.

## Public API

### Data Contracts

#### `SearchLink`

```python
@dataclass(frozen=True)
class SearchLink:
    url: str                          # Candidate download URL
    source: Optional[str] = None      # Provider tag (e.g. "firecrawl-search")
    title: Optional[str] = None       # Article title (if extracted)
    doi: Optional[str] = None         # DOI identifier (if extracted)
```

Immutable value object representing a single candidate link discovered during search or scraping.

#### `WebSearchResult`

```python
@dataclass
class WebSearchResult:
    links: List[SearchLink]           # Discovered candidate links
    query: str                        # Original search query
    provider: str                     # Provider name (e.g. "firecrawl")
    warnings: List[str]               # Non-fatal warnings from the provider
```

Result container from a search operation.

### Abstract Base

#### `WebSearchAdapter`

| Method | Signature | Description |
|--------|-----------|-------------|
| `search` | `async (query: str, *, language: Optional[str] = None) -> WebSearchResult` | Search the web for candidate download links |
| `scrape_links` | `async (url: str) -> List[SearchLink]` | Scrape a page for PDF/download links |

Constructor parameters: `api_key`, `base_url`, `timeout`, `max_results`.

### Concrete Implementation

#### `FirecrawlAdapter(WebSearchAdapter)`

Uses Firecrawl's Search API for link discovery and JSON-mode scrape for structured metadata extraction.

| Method | Signature | Description |
|--------|-----------|-------------|
| `search` | `async (query: str, *, language: Optional[str] = None) -> WebSearchResult` | Calls `client.search(query, limit=max_results)`. Extracts URLs from `result["web"]`. |
| `scrape_links` | `async (url: str) -> List[SearchLink]` | Two-phase: (1) JSON-mode scrape with schema for title/DOI/PDF URL, (2) fallback to markdown + regex extraction. |

## Internal Design

### Firecrawl JSON Scrape

`scrape_links` attempts structured extraction first:

```python
# JSON schema sent to Firecrawl
{
    "type": "object",
    "properties": {
        "title":       {"type": ["string", "null"]},
        "doi":         {"type": ["string", "null"]},
        "pdf_url":     {"type": ["string", "null"]},
        "other_links": {"type": "array", "items": {"type": "string"}},
    },
}
```

If JSON mode fails or returns no useful links, the adapter falls back to raw markdown scraping with regex-based PDF link extraction (`_PDF_URL_PATTERN`, `_PDF_LINK_PATTERN`, `_HREF_PDF_PATTERN`).

### Lazy Client Initialization

The Firecrawl `AsyncFirecrawl` client is lazy-initialized on first use via `_get_client()`. This avoids import-time side effects and keeps the module importable even when `firecrawl` is not installed (useful for tests or alternative adapter configurations).

### DOI Fallback

When JSON scrape extracts a DOI but no PDF URL, the adapter constructs a `doi.org` landing URL as a fallback:

```python
def _doi_to_url(doi: str) -> str:
    return f"https://doi.org/{doi.strip()}"
```

## Configuration

Environment variables consumed by the gateway when constructing the adapter:

| Env Var | Description |
|---------|-------------|
| `WEB_SEARCH_API_KEY` | Firecrawl API key (prefix `fc-`) |
| `WEB_SEARCH_BASE_URL` | Optional custom API endpoint (default: `https://api.firecrawl.dev`) |

## Extension Guide

### Adding a New Search Backend

1. Create a new module (e.g., `serper_adapter.py`)
2. Subclass `WebSearchAdapter`
3. Implement `search()` and `scrape_links()`
4. Register in the gateway's adapter selection logic

```python
class SerperAdapter(WebSearchAdapter):
    async def search(self, query: str, *, language=None) -> WebSearchResult:
        # Call Serper API
        ...

    async def scrape_links(self, url: str) -> List[SearchLink]:
        # Serper doesn't support scraping; return empty or use a separate scraper
        ...
```

## Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| `firecrawl-py` | ≥1.0 | Firecrawl Search + Scrape API client |
| `loguru` | — | Structured logging |

## Testing

```bash
cd backend
uv run pytest tests/core/ingest_and_digitize_data/document_acquisition/online_acquisition/ -v -k web_search
```
