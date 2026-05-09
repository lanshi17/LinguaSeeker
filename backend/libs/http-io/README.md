# http-io

Rust library for HTTP/web I/O operations in ACMG Lingua. **Not a standalone Python module** — accessed via the `rust_io.http` facade.

## From Python

```python
import rust_io.http as http_io

# Literature search
result = await http_io.fetch_one("crossref", "search", {"query": "CRISPR", "limit": 10})

# MinerU document parsing
task = await http_io.mineru_create_task("https://example.com/paper.pdf", token="...")
result = await http_io.mineru_get_result(task["task_id"], token="...")
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

## Module Structure

```
src/
├── lib.rs              # Public modules (rlib, no #[pymodule])
├── py.rs               # Python binding layer: param parsing + provider dispatch
├── client.rs           # HTTP client (reqwest + retry + proxy)
├── error.rs            # GatewayError with Python exception mapping
├── types.rs            # Shared types: Action, FetchParams, FetchResult, MinerU*
├── scraper.rs          # Generic web scraping
├── mineru.rs           # MinerU document parsing API client
└── providers/          # Data source implementations
    ├── mod.rs
    ├── crossref.rs
    ├── openalex.rs
    ├── europepmc.rs
    ├── pmc.rs
    ├── doaj.rs
    ├── jstage.rs
    └── unpaywall.rs
```

### Call Chain

```
Python call
  → rust_io.http.fetch_one        (facade, in rust-io/src/lib.rs)
    → http_io::py::fetch_one      (py.rs: param parsing, type conversion)
      → execute_provider()        (provider dispatch)
        → providers/xxx.rs        (API call via client.rs)
    → pythonize → Python dict

Python call
  → rust_io.http.mineru_create_task  (facade)
    → http_io::py::mineru_create_task (py.rs)
      → http_io::mineru::create_task  (mineru.rs: HTTP POST to MinerU API)
    → pythonize → Python dict
```

## Python API

### Literature Providers

```python
async def fetch_one(provider, action, params, timeout_ms=None, max_retries=None, proxy=None) -> dict
async def fetch_multi(providers, action, params, timeout_ms=None, max_retries=None, proxy=None) -> list[dict]
async def scrape_web(provider, action, params, timeout_ms=None, max_retries=None, proxy=None) -> dict
def scrape_html(html, css_selector) -> list[dict]
def extract_pdf_links(html, base_url) -> list[str]
```

### MinerU Document Parsing

```python
async def mineru_create_task(url, token, model_version="vlm", is_ocr=False, enable_formula=True, enable_table=True, language="ch", data_id=None, page_ranges=None, no_cache=False, cache_tolerance=900, timeout_ms=None, proxy=None) -> dict
async def mineru_get_result(task_id, token, timeout_ms=None, proxy=None) -> dict
async def mineru_batch_submit(files, token, model_version="vlm", enable_formula=True, enable_table=True, language="ch", no_cache=False, cache_tolerance=900, timeout_ms=None, proxy=None) -> dict
async def mineru_batch_result(batch_id, token, timeout_ms=None, proxy=None) -> dict
```

### params dict (literature providers)

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

### FetchResult (literature providers)

```python
{
    "provider": "crossref",
    "success": True,
    "items": [...],
    "downloads": [...],
    "warnings": [],
    "raw": {...},
    "meta": {...},
}
```

## Adding a New Literature Provider

1. Create `src/providers/myprovider.rs`:

```rust
use crate::client::HttpClient;
use crate::error::GatewayError;
use crate::types::{FetchParams, FetchResult};

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
("myprovider", Action::Search) => MyProvider::search(client, params).await,
```

Python can then call `fetch_one("myprovider", "search", {...})`.

## Dependencies

| Crate | Purpose |
|-------|---------|
| pyo3 | Python bindings |
| pyo3-async-runtimes | async fn -> Python coroutine |
| pythonize | Rust values -> Python objects |
| reqwest | HTTP client |
| tokio | Async runtime |
| scraper | HTML parsing |
| serde / serde_json | JSON serialization |
| thiserror | Error type derivation |
| url | URL parsing |
| urlencoding | URL encoding |
