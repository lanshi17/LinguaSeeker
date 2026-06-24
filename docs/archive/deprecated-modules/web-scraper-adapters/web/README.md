# Web Scrapers

> Browser-based web scrapers for academic sites that lack public APIs or require JavaScript rendering. Each scraper implements search and download for a specific regional academic publisher.
>
> **Status:** Deprecated (archived 2026-06-16). Replaced by Rust-based `net_io` HTTP providers.

## Quick Start

```python
from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.web_providers import call_web_provider

# Search via a specific web provider
result = await call_web_provider("pubscholar", "search", {
    "query": "BRCA1 variant",
    "limit": 10,
})
```

## Architecture

```
web/
├── base.py           # Shared utilities: crawl4ai_search, download_pdf_from_candidates,
│                     #   extract_pdf_links_from_html, scrape_html_elements, safe_json_loads
├── locators.py       # XPath/CSS selectors for each site's UI elements
├── pubscholar.py     # PubScholar (Chinese, CNIC/CAS)
├── chinaxiv.py       # ChinaXiv (Chinese preprints)
├── hans_publishers.py # Hans Publishers (Chinese journals)
├── cyberleninka.py   # CyberLeninka (Russian open access)
├── koreascience.py   # KoreaScience (Korean journals)
├── redalyc.py        # Redalyc / La Referencia (Spanish/Portuguese)
└── __init__.py
```

**Two-tier strategy per scraper:**

1. **Direct HTTP** (httpx): Try public APIs or static HTML parsing first (fastest)
2. **Browser automation** (crawl4ai): Fallback for JS-rendered sites

## Public API

### `base.py` -- Shared Utilities

| Function | Signature | Description |
|----------|-----------|-------------|
| `safe_json_loads` | `(text: str) -> Any` | Parse JSON, extracting from mixed content if needed |
| `extract_pdf_links_from_html` | `(html, base_url) -> List[str]` | Find PDF URLs in `<a href>` and `<meta citation_pdf_url>`. Uses Rust parser when available, falls back to selectolax. |
| `scrape_html_elements` | `(html, css_selector) -> List[Dict]` | Extract elements by CSS selector. Rust when available, selectolax fallback. |
| `download_pdf_from_candidates` | `(urls, download_path, title_stem) -> Optional[str]` | Try candidate URLs, validate `%PDF` magic bytes, save first valid PDF |

### Provider Functions

Each provider module exports `_search()` and optionally `_download()` functions:

| Module | Provider | Language | Notes |
|--------|----------|----------|-------|
| `pubscholar.py` | PubScholar | Chinese | CAS/CNIC open access |
| `chinaxiv.py` | ChinaXiv | Chinese | Preprint server |
| `hans_publishers.py` | Hans Publishers | Chinese | Open access journals |
| `cyberleninka.py` | CyberLeninka | Russian | Open access repository |
| `koreascience.py` | KoreaScience | Korean | KISTI journal platform |
| `redalyc.py` | Redalyc | Spanish/Portuguese | Latin American journals |

### `locators.py` -- Site Selectors

CSS selectors and XPath expressions for each site's search results, article pages, and PDF links.

## Internal Design

### Rust-first I/O

All HTTP calls go through `rust_io.net` when available (connection pooling, async I/O). Falls back to `httpx` when Rust extension is missing.

### PDF Validation

All downloaded PDFs validated by checking `%PDF` magic bytes before writing to disk. Invalid downloads are skipped silently.

### Crawl4ai Integration

For JS-rendered sites, `crawl4ai_search()` launches a headless browser, renders the page, then uses `LLMExtractionStrategy` to extract structured data from the rendered HTML.

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `httpx` | Async HTTP fallback |
| `selectolax` | Fast HTML parsing (fallback) |
| `crawl4ai` | Headless browser automation for JS-rendered sites |
| `rust_io.net` | Primary HTTP I/O (Rust/PyO3) |

## Testing

```bash
cd backend
uv run pytest tests/core/ingest_and_digitize_data/document_acquisition/ -v -k web
```
