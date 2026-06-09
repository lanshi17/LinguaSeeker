# net-io

> Rust library for HTTP/web I/O operations in ACMG Lingua -- literature provider APIs, HTML scraping, PDF link extraction, and MinerU document parsing. **Not a standalone Python module** -- accessed via the `rust_io.net` facade.

## From Python

```python
import rust_io.net as net_io

# Literature search
result = await net_io.fetch_one("crossref", "search", {"query": "CRISPR", "limit": 10})

# Multi-provider parallel search
results = await net_io.fetch_multi(
    ["crossref", "openalex", "europepmc"],
    "search",
    {"query": "BRCA1 variant", "limit": 5},
)

# MinerU document parsing
task = await net_io.mineru_create_task(
    "https://example.com/paper.pdf",
    token="your_token",
    language="en",
)
result = await net_io.mineru_get_result(task["task_id"], token="your_token")
```

## Build & Test

```bash
cargo build
cargo test
```

The Python extension is built from the `rust-io` crate (the facade):

```bash
cd backend
uv run maturin develop --release -m libs/rust-io/Cargo.toml
```

## Architecture

```
src/
+-- lib.rs              # Public module declarations (rlib, no #[pymodule])
+-- py.rs               # #[pyfunction] layer: param parsing, provider dispatch, MinerU wrappers
+-- client.rs           # reqwest HttpClient with retry, timeout, proxy, auth
+-- error.rs            # GatewayError enum + PyErr conversion
+-- types.rs            # Shared types: Action, FetchParams, FetchResult, MinerU*
+-- scraper.rs          # HTML scraping and PDF link extraction
+-- mineru.rs           # MinerU document parsing API client (v4)
+-- providers/          # Literature data source implementations
    +-- mod.rs
    +-- openalex.rs       # OpenAlex REST API
    +-- crossref.rs       # Crossref REST API
    +-- europepmc.rs      # Europe PMC REST API
    +-- arxiv.rs          # arXiv API
    +-- pmc.rs            # PubMed Central E-utilities
    +-- biorxiv.rs        # bioRxiv/medRxiv API
    +-- scielo.rs         # SciELO search
    +-- cinii.rs          # CiNii (Japan) API
    +-- jstage.rs         # J-STAGE (Japan Science and Technology)
    +-- doaj.rs           # Directory of Open Access Journals
    +-- unpaywall.rs      # Unpaywall OA status lookup
    +-- openaire.rs       # OpenAIRE research graph
    +-- core_search.rs    # CORE search API
    +-- base_search.rs    # BASE (Bielefeld Academic Search Engine)
```

## Literature Providers (14)

| Provider | Search | Download | Source |
|----------|--------|----------|--------|
| `openalex` | YES | NO | OpenAlex REST API |
| `crossref` | YES | NO | Crossref REST API |
| `europepmc` | YES | NO | Europe PMC REST API |
| `arxiv` | YES | NO | arXiv API |
| `pmc` | YES | NO | PubMed Central E-utilities |
| `biorxiv` | YES | NO | bioRxiv/medRxiv API |
| `scielo` | YES | NO | SciELO search |
| `cinii` | YES | NO | CiNii (Japan) API |
| `jstage` | YES | YES | J-STAGE |
| `doaj` | YES | YES | Directory of Open Access Journals |
| `unpaywall` | YES | YES | Unpaywall OA status lookup |
| `openaire` | YES | NO | OpenAIRE research graph |
| `core_search` | YES | NO | CORE search API |
| `base_search` | YES | NO | BASE academic search |

Requesting `download` for providers that do not support it returns an error. Unknown provider names return `FetchResult::failure()`.

## Python API

### Literature Providers

```python
async def fetch_one(provider, action, params, timeout_ms=None, max_retries=None, proxy=None) -> dict
async def fetch_multi(providers, action, params, timeout_ms=None, max_retries=None, proxy=None) -> list[dict]
async def scrape_web(provider, action, params, timeout_ms=None, max_retries=None, proxy=None) -> dict
def scrape_html(html, css_selector) -> list[dict]
def extract_pdf_links(html, base_url) -> list[str]
```

`fetch_multi` launches all provider requests in parallel via `futures::join_all`. Per-provider failures are captured as `FetchResult` objects with `success: false` rather than propagating exceptions.

### MinerU Document Parsing (API v4)

| Function | Description |
|----------|-------------|
| `mineru_create_task(url, token, ...)` | Submit single document for parsing |
| `mineru_get_result(task_id, token, ...)` | Poll single task result |
| `mineru_batch_submit(files, token, ...)` | Submit batch of URLs |
| `mineru_batch_result(batch_id, token, ...)` | Get batch results |
| `mineru_create_upload_url(filename, token, ...)` | Get pre-signed upload URL for one local file |
| `mineru_create_batch_upload_urls(files, token, ...)` | Get pre-signed upload URLs for multiple local files |
| `mineru_upload_local_files(file_paths, token, ...)` | Create upload URLs + PUT files (all-in-one) |
| `mineru_upload_local_file(upload_url, file_path, ...)` | Upload a single file to a pre-signed URL |

## HttpClient

| Feature | Default | Notes |
|---------|---------|-------|
| Timeout | 30,000 ms | Configurable per-call via `timeout_ms` |
| Max retries | 2 (3 total attempts) | Exponential backoff starting at 1s, capped at 2^20 ms |
| User-Agent | `acmg-lingua-io/0.1.0` | |
| Redirects | Up to 10 | |
| Gzip | Enabled | |

Retry only applies to `get_json` (provider search calls). MinerU API calls do not retry.

## Error Handling

| Rust variant | Python exception | Typical cause |
|-------------|-----------------|---------------|
| `Http(reqwest::Error)` | `ConnectionError` | Timeout, DNS failure, non-2xx |
| `Json(serde_json::Error)` | `ValueError` | Malformed provider response |
| `Io(std::io::Error)` | `OSError` | File read failure (MinerU upload) |
| `Url(url::ParseError)` | `ValueError` | Malformed URL |
| `Provider { provider, message }` | `RuntimeError` | Unknown provider or unsupported action |
| `Other(String)` | `RuntimeError` | Catch-all |

## Dependencies

| Crate | Purpose |
|-------|---------|
| reqwest | HTTP client (rustls, gzip, SOCKS proxy) |
| scraper | HTML parsing + CSS selectors |
| tokio | Async runtime |
| serde / serde_json | Serialization |
| url / urlencoding | URL handling |
| pythonize | Rust struct -> Python dict |

## Testing

```bash
cd backend/libs/net-io
cargo test
```

Unit tests cover: HTTP client retry/backoff, error-to-PyErr mapping, HTML scraping, PDF link extraction, and individual provider search functions. Integration with real provider APIs requires network access.
