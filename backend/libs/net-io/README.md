# net-io

> Rust library for HTTP/web I/O operations in ACMG Lingua — literature provider APIs, HTML scraping, PDF link extraction, and MinerU document parsing. **Not a standalone Python module** — accessed via the `rust_io.net` facade.

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
Python call
  → rust_io.net.<function>         (facade, in rust-io/src/lib.rs)
    → net_io::py::<function>       (py.rs: param parsing, type conversion)
      → execute_provider()         (provider dispatch by name + action)
        → providers/<name>.rs      (API call via client.rs)
      → pythonize → Python dict

Python call (MinerU)
  → rust_io.net.mineru_create_task   (facade)
    → net_io::py::mineru_create_task (py.rs: construct request, create client)
      → net_io::mineru::create_task  (mineru.rs: POST to MinerU API v4)
    → pythonize → Python dict
```

### Module Structure

```
src/
├── lib.rs              # Public module declarations (rlib, no #[pymodule])
├── py.rs               # #[pyfunction] layer: param parsing, provider dispatch, MinerU wrappers
├── client.rs           # reqwest HttpClient with retry, timeout, proxy, auth
├── error.rs            # GatewayError enum + PyErr conversion
├── types.rs            # Shared types: Action, FetchParams, FetchResult, MinerU*
├── scraper.rs          # HTML scraping and PDF link extraction
├── mineru.rs           # MinerU document parsing API client (v4)
└── providers/          # Literature data source implementations
    ├── mod.rs
    ├── crossref.rs       # Crossref REST API
    ├── openalex.rs       # OpenAlex REST API
    ├── europepmc.rs      # Europe PMC REST API
    ├── pmc.rs            # PubMed Central E-utilities + OA subset
    ├── doaj.rs           # Directory of Open Access Journals
    ├── jstage.rs         # J-STAGE (Japan Science and Technology)
    └── unpaywall.rs      # Unpaywall OA status lookup
```

## Python API

### Literature Providers

```python
async def fetch_one(
    provider: str,
    action: str,
    params: dict,
    timeout_ms: int | None = None,      # default 30_000
    max_retries: int | None = None,      # default 2
    proxy: str | None = None,
) -> dict

async def fetch_multi(
    providers: list[str],
    action: str,
    params: dict,
    timeout_ms: int | None = None,
    max_retries: int | None = None,
    proxy: str | None = None,
) -> list[dict]

async def scrape_web(
    provider: str,
    action: str,
    params: dict,
    timeout_ms: int | None = None,
    max_retries: int | None = None,
    proxy: str | None = None,
) -> dict

def scrape_html(html: str, css_selector: str) -> list[dict]
def extract_pdf_links(html: str, base_url: str) -> list[str]
```

`fetch_multi` launches all provider requests in parallel via `futures::join_all`. Per-provider failures (HTTP errors, timeouts, unknown providers) are captured as `FetchResult` objects with `success: false` rather than propagating exceptions — a single provider failure does not abort the entire batch.

### Provider × Action Support Matrix

| Provider   | `search` | `download` |
|------------|----------|------------|
| `crossref` | YES | NO |
| `openalex` | YES | NO |
| `europepmc`| YES | NO |
| `pmc`      | YES | NO |
| `doaj`     | YES | YES |
| `jstage`   | YES | YES |
| `unpaywall`| YES | YES |

Requesting `download` for `crossref`, `openalex`, `europepmc`, or `pmc` returns an error. Unknown provider names return `FetchResult::failure()`.

### `params` dict (literature providers)

```python
{
    "query": "CRISPR gene editing",
    "limit": 20,
    "raw": False,
    "selected_index": 0,
    "selected_title": "...",
    "detail_link": "https://...",
    "identifiers": {
        "doi": "10.1234/xxx",
        "pmid": "12345678",
        "pmcid": "PMC1234567",
        "issn": "1234-5678",
    },
}
```

All fields are optional. `identifiers` is a nested dict; each sub-field (`doi`, `pmid`, `pmcid`, `issn`) is independently `Optional[str]`.

### `FetchResult` (returned from all provider functions)

```python
{
    "provider": "crossref",
    "success": True,
    "items": [...],          # list of matched records as JSON objects
    "downloads": [...],      # download URLs or results
    "warnings": [...],       # non-fatal warnings (e.g. partial results)
    "raw": {...},            # raw provider response (when available)
    "meta": {...},           # provider-specific metadata
}
```

### `scrape_html` return value

```python
[{
    "text": "element text content",
    "html": "<inner>HTML</inner>",
    "tag_name": "div",
    "attrs": {"class": "item", "href": "..."},
}, ...]
```

### MinerU Document Parsing

```python
async def mineru_create_task(
    url: str,
    token: str,
    model_version: str | None = None,     # default "vlm"
    is_ocr: bool | None = None,            # default False
    enable_formula: bool | None = None,    # default True
    enable_table: bool | None = None,      # default True
    language: str | None = None,            # default "ch"
    data_id: str | None = None,
    page_ranges: str | None = None,
    no_cache: bool | None = None,          # default False
    cache_tolerance: int | None = None,    # default 900 (seconds)
    timeout_ms: int | None = None,
    proxy: str | None = None,
) -> dict

async def mineru_get_result(
    task_id: str,
    token: str,
    timeout_ms: int | None = None,
    proxy: str | None = None,
) -> dict

async def mineru_batch_submit(
    files: list[dict],                     # each: {"url": str, "data_id"?, "is_ocr"?, "page_ranges"?}
    token: str,
    model_version: str | None = None,
    enable_formula: bool | None = None,
    enable_table: bool | None = None,
    language: str | None = None,
    no_cache: bool | None = None,
    cache_tolerance: int | None = None,
    timeout_ms: int | None = None,
    proxy: str | None = None,
) -> dict


async def mineru_create_upload_url(
    filename: str,
    token: str,
    content_type: str | None = None,
    model_version: str | None = None,
    is_ocr: bool | None = None,
    enable_formula: bool | None = None,
    enable_table: bool | None = None,
    language: str | None = None,
    data_id: str | None = None,
    page_ranges: str | None = None,
    no_cache: bool | None = None,
    cache_tolerance: int | None = None,
    timeout_ms: int | None = None,
    proxy: str | None = None,
) -> dict                                  # returns code/msg/data with pre-signed upload URL
async def mineru_create_batch_upload_urls(
    files: list[dict],                     # each: {"name": str, "data_id"?, "is_ocr"?, "page_ranges"?}
    token: str,
    model_version: str | None = None,
    enable_formula: bool | None = None,
    enable_table: bool | None = None,
    language: str | None = None,
    callback: str | None = None,
    seed: str | None = None,               # required by MinerU when callback is set
    extra_formats: list[str] | None = None, # supported by MinerU: "docx", "html", "latex"
    timeout_ms: int | None = None,
    proxy: str | None = None,
) -> dict                                  # returns code/msg/data.batch_id/data.file_urls

async def mineru_batch_result(
    batch_id: str,
    token: str,
    timeout_ms: int | None = None,
    proxy: str | None = None,
) -> dict

async def mineru_upload_local_file(
    upload_url: str,
    file_path: str,
    content_type: str | None = None,       # MinerU docs recommend omitting Content-Type
    timeout_ms: int | None = None,
    proxy: str | None = None,
) -> dict

async def mineru_upload_local_files(
    file_paths: list[str],
    token: str,
    model_version: str | None = None,
    enable_formula: bool | None = None,
    enable_table: bool | None = None,
    language: str | None = None,
    data_ids: list[str] | None = None,     # must match file_paths length when provided
    is_ocr: bool | None = None,
    page_ranges: str | None = None,
    callback: str | None = None,
    seed: str | None = None,
    extra_formats: list[str] | None = None,
    timeout_ms: int | None = None,
    proxy: str | None = None,
) -> dict                                  # creates upload URLs, PUTs files, then returns batch response
```

All MinerU functions target the MinerU API v4 (`https://mineru.net/api/v4`). Authentication is via `Authorization: Bearer <token>` header.

## Internal Design

### HttpClient

`HttpClient` wraps `reqwest::Client` and provides:

| Feature | Default | Notes |
|---------|---------|-------|
| Timeout | 30,000 ms | Configurable per-call via `timeout_ms` |
| Max retries | 2 (3 total attempts) | Exponential backoff starting at 1s, capped at 2^20 ms |
| User-Agent | `acmg-lingua-io/0.1.0` | |
| Redirects | Up to 10 | |
| Gzip | Enabled | |
| Proxy | None | Optional per-call via `proxy` |

Retry only applies to `get_json` (provider search calls). `get_text`, `post_json`, and `get_json_with_auth` do not retry.

Backoff formula: `delay_ms = 1000 * 2^(attempt - 1)`, capped at `2^20 * 1000 ≈ 17.5 minutes`. This means attempt 0 → instant, attempt 1 → 1s, attempt 2 → 2s.

### Error Handling

`GatewayError` variants map to Python exceptions:

| Rust variant | Python exception |
|-------------|-----------------|
| `Http(reqwest::Error)` | `ConnectionError` |
| `Json(serde_json::Error)` | `ValueError` |
| `Io(std::io::Error)` | `OSError` |
| `Url(url::ParseError)` | `ValueError` |
| `Provider { provider, message }` | `RuntimeError` |
| `Other(String)` | `RuntimeError` |

The `From<GatewayError> for PyErr` impl handles this mapping globally, so any `?` in Rust code automatically produces the correct Python exception type.

### `scrape_web` vs provider functions

`scrape_web` uses `scraper::WebScraper` which fetches the page HTML via `client.get_text()` and extracts elements matching a CSS selector. The action parameter is currently ignored — it derives the target URL from `params.detail_link` (falling back to `params.query`). This is suitable for providers that don't have structured APIs and require raw web scraping.

`fetch_one` with known providers uses structured API calls (REST/JSON). Use `fetch_one` for API-based providers, `scrape_web` for scraping-based providers like CyberLeninka, Hans Publishers, or PubScholar.

## Usage Patterns

### Single-provider search with error handling

```python
import rust_io.net as net_io

result = await net_io.fetch_one(
    "crossref",
    "search",
    {"query": "BRCA1 pathogenic variant", "limit": 10},
    timeout_ms=15_000  # lower timeout for snappy response
)

if result["success"]:
    for item in result["items"]:
        print(item.get("title"))
else:
    print(f"Search failed: {result['warnings']}")
```

### Parallel multi-provider search

```python
results = await net_io.fetch_multi(
    ["crossref", "openalex", "europepmc", "pmc"],
    "search",
    {"query": "TP53 mutation prognosis", "limit": 5},
)

for r in results:
    if r["success"]:
        print(f"{r['provider']}: {len(r['items'])} results")
    else:
        print(f"{r['provider']}: FAILED - {r['warnings']}")
```

### MinerU document parsing workflow

```python
# Start a parsing task
task = await net_io.mineru_create_task(
    "https://example.com/papers/variant-analysis.pdf",
    token="your_mineru_token",
    language="en",
    enable_table=True,
    enable_formula=True,
)

task_id = task["task_id"]

# Poll until complete
import asyncio
while True:
    result = await net_io.mineru_get_result(task_id, token="your_mineru_token")
    if result.get("status") == "done":
        print(f"Parsing complete: {result}")
        break
    await asyncio.sleep(5)
```

### HTML scraping and PDF link extraction

```python
# Fetch and parse HTML via a scraping provider
html_result = await net_io.scrape_web(
    "cyberleninka",
    "search",
    {"query": "https://cyberleninka.ru/search?q=CRISPR"},
)
# Then extract PDF links from the raw HTML
# (scrape_web returns parsed elements; use get_text + scrape_html for raw HTML)
```

```python
# Extract PDF links from known HTML
pdfs = net_io.extract_pdf_links(
    '<html><body><a href="/paper.pdf">PDF</a>'
    '<meta name="citation_pdf_url" content="https://doi.org/10.1234/paper.pdf">'
    '</body></html>',
    "https://example.com"
)
# pdfs = ["https://example.com/paper.pdf", "https://doi.org/10.1234/paper.pdf"]
```

## Adding a New Literature Provider

1. Create `src/providers/myprovider.rs`:

```rust
use crate::client::HttpClient;
use crate::error::GatewayError;
use crate::types::{Action, FetchParams, FetchResult};

pub struct MyProvider;

impl MyProvider {
    pub async fn search(
        client: &HttpClient,
        params: &FetchParams,
    ) -> Result<FetchResult, GatewayError> {
        let query = params.query.as_deref().unwrap_or_default();
        let params = serde_json::json!({ "q": query, "size": params.limit.unwrap_or(20) });
        let json = client.get_json("https://api.example.com/search", &params).await?;

        let items = json
            .get("results")
            .and_then(|v| v.as_array())
            .map(|a| a.to_vec())
            .unwrap_or_default();

        Ok(FetchResult {
            provider: "myprovider".into(),
            success: true,
            items,
            downloads: vec![],
            warnings: vec![],
            raw: Some(json),
            meta: None,
        })
    }
}
```

2. Register in `src/providers/mod.rs`:

```rust
mod myprovider;
pub use myprovider::MyProvider;
```

3. Add dispatch in `src/py.rs` `execute_provider()`:

```rust
use crate::providers::MyProvider;
// ...
("myprovider", Action::Search) => MyProvider::search(client, params).await,
```

For download support, add a `download` method and a second dispatch arm with `Action::Download`.

## Dependencies

| Crate | Version | Purpose |
|-------|---------|---------|
| pyo3 | 0.28.2 | Python bindings |
| pyo3-async-runtimes | 0.28 | async fn → Python coroutine |
| pythonize | 0.28 | Rust values → Python objects |
| reqwest | 0.13 | HTTP client (rustls, gzip, SOCKS proxy) |
| tokio | 1 | Async runtime |
| futures | 0.3 | `join_all` for parallel provider dispatch in `fetch_multi` |
| scraper | 0.26 | HTML parsing and CSS selector extraction |
| serde / serde_json | 1 | JSON serialization/deserialization |
| thiserror | 2 | Error type derivation |
| url | 2 | URL parsing and resolution |
| urlencoding | 2 | URL encoding utilities |

Build system: [maturin](https://www.maturin.rs/) (>= 1.13), via the `rust-io` crate's `pyproject.toml`.

## Testing

Run all tests with `cargo test`:

```bash
cd backend/libs/net-io
cargo test
```

Test coverage includes:

| Module | Tests | What's covered |
|--------|-------|---------------|
| `client.rs` | 2 tests | Retry backoff capping, URL percent-encoding (DOI edge case) |
| `error.rs` | 3 tests | Error-to-PyErr mapping: JSON→ValueError, URL→ValueError, Provider→RuntimeError |
| `scraper.rs` | 10 tests | HTML scraping (element extraction, empty selector, invalid CSS, attribute preservation), PDF link extraction (anchors, meta tags, relative URL resolution, dedup, empty case, download pattern) |
| `crossref.rs` | inline | Provider-level tests |
| `europepmc.rs` | inline | Provider-level tests |

Provider test modules use `#[cfg(test)]` and are run as part of `cargo test`. Integration with real provider APIs requires network access and is not covered by unit tests.

Not covered:
- `fetch_one` / `fetch_multi` / `scrape_web` end-to-end (require live provider APIs)
- MinerU API functions (require valid MinerU token)
- `fetch_multi` parallel execution behavior

## Security Notes

- **MinerU tokens**: Passed per-call via the `token` kwarg. Never hardcoded in source or committed to version control. The crate does not read tokens from the environment — callers are responsible for secure token management.
- **Unpaywall email**: Retrieved from the `UNPAYWALL_EMAIL` environment variable at runtime in `unpaywall.rs`. Set this in `.env.local` or your deployment environment.
- **S3 credentials** (via `files-io`): Can be passed explicitly as kwargs or resolved from the AWS credential chain. Never log or serialize credentials in `FetchResult` or error messages.
- **Archive extraction**: Both tar/tar.gz and ZIP extraction validate all entry paths to prevent zip-slip / path traversal attacks. Symlink entries in archives are rejected. See `files-io` crate for details.
- **Proxy URLs**: May contain credentials if using authenticated proxies. These are not logged, but callers should avoid passing proxy URLs with embedded credentials in clear text over untrusted channels.

## Performance Notes

- **Provider parallelism**: `fetch_multi` uses `futures::join_all` to run all provider requests concurrently on the tokio runtime. There is no global rate limiter or connection pool — all providers share the same `reqwest::Client` (created per `HttpClient` instance). For large provider sets, consider external throttling.
- **Retry strategy**: Only `get_json` (provider search) has retry with exponential backoff (1s base, capped at ~17.5 min). `get_text`, `post_json`, `put_bytes`, and `get_json_with_auth` are single-attempt. This means MinerU API calls do not retry on transient failures — wrap them in retry logic at the Python level if needed.
- **HTML scraping**: `scrape_html` and `extract_pdf_links` parse the full HTML document in memory. For very large HTML pages (>10MB), consider streaming or chunking at the Python level before calling these functions.
- **Provider response parsing**: All provider `search` functions parse the full JSON response into `Vec<Value>`. No streaming or pagination is implemented — the `limit` parameter controls how many results the provider returns, not how many are parsed.
- **Memory**: Each `HttpClient` carries a `reqwest::Client` (connection pool, TLS session cache). Creating a new client per call (`fetch_one`, `fetch_multi`, each MinerU call) is intentional for isolation but means connection reuse is limited to the duration of a single Python coroutine.

## Internal Rust API

For developers modifying or extending the crate:

### `HttpClient` (client.rs)

```rust
impl HttpClient {
    pub fn new(timeout_ms: Option<u64>, max_retries: Option<u32>, proxy: Option<&str>) -> Result<Self, GatewayError>;
    pub async fn get_json(&self, url: &str, query: &Value) -> Result<Value, GatewayError>;       // with retry
    pub async fn get_text(&self, url: &str) -> Result<String, GatewayError>;                      // no retry
    pub async fn post_json(&self, url: &str, body: &Value, auth_header: Option<&str>) -> Result<Value, GatewayError>;
    pub async fn put_bytes(&self, url: &str, bytes: Vec<u8>, content_type: Option<&str>) -> Result<Value, GatewayError>;
    pub async fn get_json_with_auth(&self, url: &str, auth_header: Option<&str>) -> Result<Value, GatewayError>;
}
```

Defaults: `DEFAULT_TIMEOUT_MS = 30_000`, `DEFAULT_MAX_RETRIES = 2`, `BACKOFF_BASE_MS = 1000`.

### Provider pattern

Each provider is a unit struct with one or more async associated functions:

```rust
pub struct CrossrefProvider;
impl CrossrefProvider {
    pub async fn search(client: &HttpClient, params: &FetchParams) -> Result<FetchResult, GatewayError>;
}
```

All providers return `FetchResult`. The `execute_provider` function in `py.rs` dispatches by matching on `(provider_name, action)` tuples.

### `WebScraper` (scraper.rs)

```rust
pub fn scrape_html(html: &str, css_selector: &str) -> Result<Vec<ScrapedElement>, GatewayError>;
pub fn extract_pdf_links(html: &str, base_url: &str) -> Vec<String>;
```

`scrape_provider` is the async entry point for the `scrape_web` pyfunction. It fetches HTML via `HttpClient::get_text` and extracts elements using `WebScraper`.

### `GatewayError` (error.rs)

Six variants: `Http`, `Json`, `Io`, `Url`, `Provider { provider, message }`, `Other(String)`. All implement `From<...> for GatewayError` so `?` propagation works. The `From<GatewayError> for PyErr` impl maps each variant to the semantically correct Python exception type automatically — no manual error conversion needed at the PyO3 boundary.
