# Rename literature-io to http-io + Add MinerU API Support

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rename the `literature-io` Rust crate to `http-io` (reflecting its role as the HTTP/web I/O layer) and add MinerU document parsing API support as a new provider.

**Architecture:** The `http-io` crate remains an `rlib` accessed via the `rust-io` facade (`rust_io.http` Python module). MinerU integration adds 4 new async Python functions (`mineru_create_task`, `mineru_get_result`, `mineru_batch_submit`, `mineru_batch_result`) backed by a new `mineru.rs` module with strongly-typed request structs and `serde_json::Value` responses (to avoid deserialization failures from API changes). The existing literature provider functions stay unchanged under the same crate.

**Tech Stack:** Rust (reqwest, serde, tokio, pyo3), Python (gateway integration)

---

## Part A: Rename literature-io → http-io

### Task 1: Rename crate directory and Cargo.toml

**Files:**
- Rename: `backend/libs/literature-io/` → `backend/libs/http-io/`
- Modify: `backend/libs/http-io/Cargo.toml`
- Modify: `backend/libs/rust-io/Cargo.toml`

**Step 1: Rename directory**

```bash
cd /data/[redacted-user]/Projects/01_ACMG_Lingua
git mv backend/libs/literature-io backend/libs/http-io
```

**Step 2: Update http-io/Cargo.toml**

Change `name` and `lib.name`:

```toml
[package]
name = "http-io"
version = "0.1.0"
edition = "2024"
description = "High-performance HTTP/web I/O for ACMG Lingua"

[lib]
name = "http_io"
crate-type = ["rlib"]
```

Keep all `[dependencies]` unchanged.

**Step 3: Update rust-io/Cargo.toml dependency**

```toml
[dependencies]
pyo3 = { version = "0.28.2", features = ["extension-module"] }
pyo3-async-runtimes = { version = "0.28", features = ["tokio-runtime"] }
files-io = { path = "../files-io" }
http-io = { path = "../http-io" }
```

**Step 4: Verify it compiles**

```bash
cd backend/libs/http-io && cargo check
cd backend/libs/rust-io && cargo check
```

Expected: both compile without errors (just a rename, no code changes yet).

**Step 5: Commit**

```bash
git add backend/libs/http-io backend/libs/rust-io/Cargo.toml
git commit -m "refactor: rename literature-io crate to http-io"
```

---

### Task 2: Update rust-io facade to use http_io module name

**Files:**
- Modify: `backend/libs/rust-io/src/lib.rs`

**Step 1: Update lib.rs imports and registrations**

Replace all `literature_io::` references with `http_io::`. Change the Python submodule name from `"literature"` to `"http"`, and the `register_submodule` name from `"rust_io.literature"` to `"rust_io.http"`.

```rust
use pyo3::prelude::*;
use pyo3::types::PyDict;

fn register_submodule(
    parent: &Bound<'_, PyModule>,
    full_name: &str,
    submodule: &Bound<'_, PyModule>,
) -> PyResult<()> {
    parent.add_submodule(submodule)?;
    parent
        .py()
        .import("sys")?
        .getattr("modules")?
        .cast::<PyDict>()?
        .set_item(full_name, submodule)?;
    Ok(())
}

#[pymodule]
fn rust_io(m: &Bound<'_, PyModule>) -> PyResult<()> {
    let http = PyModule::new(m.py(), "http")?;
    http.add_function(wrap_pyfunction!(http_io::py::fetch_one, &http)?)?;
    http.add_function(wrap_pyfunction!(http_io::py::fetch_multi, &http)?)?;
    http.add_function(wrap_pyfunction!(http_io::py::scrape_web, &http)?)?;
    http.add_function(wrap_pyfunction!(http_io::py::scrape_html, &http)?)?;
    http.add_function(wrap_pyfunction!(http_io::py::extract_pdf_links, &http)?)?;
    register_submodule(m, "rust_io.http", &http)?;

    let files = PyModule::new(m.py(), "files")?;
    files.add_class::<files_io::py::file::File>()?;
    files.add_function(wrap_pyfunction!(
        files_io::py::parallel::batch_copy,
        &files
    )?)?;
    files.add_function(wrap_pyfunction!(
        files_io::py::parallel::batch_compress,
        &files
    )?)?;
    files.add_function(wrap_pyfunction!(
        files_io::py::parallel::batch_copy_async,
        &files
    )?)?;
    files.add_function(wrap_pyfunction!(
        files_io::py::dedup::check_duplicate,
        &files
    )?)?;
    files.add_function(wrap_pyfunction!(files_io::py::dedup::batch_hash, &files)?)?;
    files.add_function(wrap_pyfunction!(
        files_io::py::utils::compute_sha256,
        &files
    )?)?;
    files.add_function(wrap_pyfunction!(files_io::py::utils::write_file, &files)?)?;
    files.add_function(wrap_pyfunction!(
        files_io::py::utils::validate_pdf_magic,
        &files
    )?)?;
    register_submodule(m, "rust_io.files", &files)?;

    Ok(())
}
```

**Step 2: Verify compilation**

```bash
cd backend/libs/rust-io && cargo check
```

**Step 3: Commit**

```bash
git add backend/libs/rust-io/src/lib.rs
git commit -m "refactor: update rust-io facade to use http_io module name"
```

---

### Task 3: Update Python imports from rust_io.literature to rust_io.http

**Files:**
- Modify: `backend/src/core/ingest_and_digitize_data/document_acquisition/online_acquisition/gateway.py`
- Modify: `backend/src/core/ingest_and_digitize_data/document_acquisition/online_acquisition/web/base.py`
- Modify: `backend/tests/core/ingest_and_digitize_data/document_acquisition/online_acquisition/test_gateway.py`

**Step 1: Update gateway.py**

Replace all `import rust_io.literature as literature_io` with `import rust_io.http as http_io` and update all call sites from `literature_io.` to `http_io.`. Also update docstrings and comments.

Key changes:
- Line 1: docstring `literature_io` → `http_io`
- Line 128: docstring `literature_io.fetch_one` → `http_io.fetch_one`
- Line 156: docstring `literature_io FetchResult` → `http_io FetchResult`
- Line 194: docstring `literature_io.fetch_one` → `http_io.fetch_one`
- Line 196: `import rust_io.literature as literature_io` → `import rust_io.http as http_io`
- Line 200: error message `"literature_io not available"` → `"http_io not available"`
- Line 206: `literature_io.fetch_one` → `http_io.fetch_one`

**Step 2: Update web/base.py**

Replace `import rust_io.literature as literature_io` with `import rust_io.http as http_io` and update calls:
- Line 40: `import rust_io.literature as literature_io` → `import rust_io.http as http_io`
- Line 41: `literature_io.extract_pdf_links` → `http_io.extract_pdf_links`
- Line 63: `import rust_io.literature as literature_io` → `import rust_io.http as http_io`
- Line 64: `literature_io.scrape_html` → `http_io.scrape_html`

**Step 3: Update test_gateway.py**

Update mock patch strings from `rust_io.literature` to `rust_io.http` and `literature_io` references in test names/comments.

**Step 4: Run tests**

```bash
cd backend && uv run pytest tests/core/ingest_and_digitize_data/document_acquisition/online_acquisition/test_gateway.py -v
```

**Step 5: Commit**

```bash
git add backend/src/core/ingest_and_digitize_data/document_acquisition/online_acquisition/ \
       backend/tests/core/ingest_and_digitize_data/document_acquisition/online_acquisition/test_gateway.py
git commit -m "refactor: update Python imports from rust_io.literature to rust_io.http"
```

---

### Task 4: Update http-io README and documentation

**Files:**
- Modify: `backend/libs/http-io/README.md`
- Modify: `AGENTS.md` (if it references literature-io)

**Step 1: Update README.md**

Rewrite `backend/libs/http-io/README.md`:

```markdown
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
├── types.rs            # Shared types: Action, FetchParams, FetchResult
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
```

**Step 2: Commit**

```bash
git add backend/libs/http-io/README.md
git commit -m "docs: update http-io README with MinerU API docs"
```

---

## Part B: Add MinerU API Support

### Task 5: Add MinerU types to types.rs

**Files:**
- Modify: `backend/libs/http-io/src/types.rs`

**Step 1: Add MinerU type definitions**

Append to `types.rs`:

```rust
// ── MinerU API types ─────────────────────────────────────────────────

// NOTE: MinerUModelVersion, MinerUTaskState, MinerUExtractProgress were
// planned as strongly-typed response types but deliberately NOT implemented.
// All MinerU functions return serde_json::Value instead, because:
//   - MinerU API response schema is not versioned or guaranteed stable
//   - Value avoids deserialization failures when the API adds/renames fields
//   - Consistent with literature providers which also return Value in FetchResult.items
// model_version uses Option<String> rather than the MinerUModelVersion enum.

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MinerUCreateTaskRequest {
    pub url: String,
    pub model_version: Option<String>,
    pub is_ocr: Option<bool>,
    pub enable_formula: Option<bool>,
    pub enable_table: Option<bool>,
    pub language: Option<String>,
    pub data_id: Option<String>,
    pub page_ranges: Option<String>,
    pub no_cache: Option<bool>,
    pub cache_tolerance: Option<u32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MinerUBatchFileEntry {
    pub url: String,
    pub data_id: Option<String>,
    pub is_ocr: Option<bool>,
    pub page_ranges: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MinerUBatchSubmitRequest {
    pub files: Vec<MinerUBatchFileEntry>,
    pub model_version: Option<String>,
    pub enable_formula: Option<bool>,
    pub enable_table: Option<bool>,
    pub language: Option<String>,
    pub no_cache: Option<bool>,
    pub cache_tolerance: Option<u32>,
}
```

**Step 2: Verify compilation**

```bash
cd backend/libs/http-io && cargo check
```

**Step 3: Commit**

```bash
git add backend/libs/http-io/src/types.rs
git commit -m "feat: add MinerU API type definitions"
```

---

### Task 6: Implement MinerU client module (mineru.rs)

**Files:**
- Create: `backend/libs/http-io/src/mineru.rs`
- Modify: `backend/libs/http-io/src/lib.rs`

**Step 1: Write failing tests for MinerU module**

Create `backend/libs/http-io/src/mineru.rs` with tests first:

```rust
use crate::client::HttpClient;
use crate::error::GatewayError;
use crate::types::{
    MinerUBatchFileEntry, MinerUBatchSubmitRequest, MinerUCreateTaskRequest,
};
use serde_json::Value;

const MINERU_BASE_URL: &str = "https://mineru.net/api/v4";

fn auth_header(token: &str) -> String {
    format!("Bearer {token}")
}

/// Create a single document parsing task.
/// POST /extract/task
pub async fn create_task(
    client: &HttpClient,
    token: &str,
    request: &MinerUCreateTaskRequest,
) -> Result<Value, GatewayError> {
    let url = format!("{MINERU_BASE_URL}/extract/task");
    let body = build_create_task_body(request);
    post_json_with_auth(&client, &url, token, &body).await
}

/// Get single task result.
/// GET /extract/task/{task_id}
pub async fn get_result(
    client: &HttpClient,
    token: &str,
    task_id: &str,
) -> Result<Value, GatewayError> {
    let url = format!("{MINERU_BASE_URL}/extract/task/{task_id}");
    get_with_auth(&client, &url, token).await
}

/// Submit batch URL-based parsing tasks.
/// POST /extract/task/batch
pub async fn batch_submit(
    client: &HttpClient,
    token: &str,
    request: &MinerUBatchSubmitRequest,
) -> Result<Value, GatewayError> {
    let url = format!("{MINERU_BASE_URL}/extract/task/batch");
    let body = build_batch_submit_body(request);
    post_json_with_auth(&client, &url, token, &body).await
}

/// Get batch results.
/// GET /extract-results/batch/{batch_id}
pub async fn batch_result(
    client: &HttpClient,
    token: &str,
    batch_id: &str,
) -> Result<Value, GatewayError> {
    let url = format!("{MINERU_BASE_URL}/extract-results/batch/{batch_id}");
    get_with_auth(&client, &url, token).await
}

fn build_create_task_body(request: &MinerUCreateTaskRequest) -> Value {
    let mut body = serde_json::json!({ "url": request.url });
    if let Some(ref v) = request.model_version {
        body["model_version"] = Value::String(v.clone());
    }
    if let Some(v) = request.is_ocr {
        body["is_ocr"] = Value::Bool(v);
    }
    if let Some(v) = request.enable_formula {
        body["enable_formula"] = Value::Bool(v);
    }
    if let Some(v) = request.enable_table {
        body["enable_table"] = Value::Bool(v);
    }
    if let Some(ref v) = request.language {
        body["language"] = Value::String(v.clone());
    }
    if let Some(ref v) = request.data_id {
        body["data_id"] = Value::String(v.clone());
    }
    if let Some(ref v) = request.page_ranges {
        body["page_ranges"] = Value::String(v.clone());
    }
    if let Some(v) = request.no_cache {
        body["no_cache"] = Value::Bool(v);
    }
    if let Some(v) = request.cache_tolerance {
        body["cache_tolerance"] = Value::from(v);
    }
    body
}

fn build_batch_submit_body(request: &MinerUBatchSubmitRequest) -> Value {
    let files: Vec<Value> = request
        .files
        .iter()
        .map(|f| {
            let mut entry = serde_json::json!({ "url": f.url });
            if let Some(ref v) = f.data_id {
                entry["data_id"] = Value::String(v.clone());
            }
            if let Some(v) = f.is_ocr {
                entry["is_ocr"] = Value::Bool(v);
            }
            if let Some(ref v) = f.page_ranges {
                entry["page_ranges"] = Value::String(v.clone());
            }
            entry
        })
        .collect();

    let mut body = serde_json::json!({ "files": files });
    if let Some(ref v) = request.model_version {
        body["model_version"] = Value::String(v.clone());
    }
    if let Some(v) = request.enable_formula {
        body["enable_formula"] = Value::Bool(v);
    }
    if let Some(v) = request.enable_table {
        body["enable_table"] = Value::Bool(v);
    }
    if let Some(ref v) = request.language {
        body["language"] = Value::String(v.clone());
    }
    if let Some(v) = request.no_cache {
        body["no_cache"] = Value::Bool(v);
    }
    if let Some(v) = request.cache_tolerance {
        body["cache_tolerance"] = Value::from(v);
    }
    body
}

async fn post_json_with_auth(
    client: &HttpClient,
    url: &str,
    token: &str,
    body: &Value,
) -> Result<Value, GatewayError> {
    let resp = client
        .post_json(url, body, Some(&auth_header(token)))
        .await?;
    Ok(resp)
}

async fn get_with_auth(
    client: &HttpClient,
    url: &str,
    token: &str,
) -> Result<Value, GatewayError> {
    let resp = client
        .get_json_with_auth(url, Some(&auth_header(token)))
        .await?;
    Ok(resp)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_build_create_task_body_defaults() {
        let req = MinerUCreateTaskRequest {
            url: "https://example.com/test.pdf".into(),
            model_version: None,
            is_ocr: None,
            enable_formula: None,
            enable_table: None,
            language: None,
            data_id: None,
            page_ranges: None,
            no_cache: None,
            cache_tolerance: None,
        };
        let body = build_create_task_body(&req);
        assert_eq!(body["url"], "https://example.com/test.pdf");
        assert!(body.get("model_version").is_none());
        assert!(body.get("is_ocr").is_none());
    }

    #[test]
    fn test_build_create_task_body_full() {
        let req = MinerUCreateTaskRequest {
            url: "https://example.com/test.pdf".into(),
            model_version: Some("vlm".into()),
            is_ocr: Some(true),
            enable_formula: Some(true),
            enable_table: Some(false),
            language: Some("en".into()),
            data_id: Some("abc-123".into()),
            page_ranges: Some("1-10".into()),
            no_cache: Some(true),
            cache_tolerance: Some(600),
        };
        let body = build_create_task_body(&req);
        assert_eq!(body["model_version"], "vlm");
        assert_eq!(body["is_ocr"], true);
        assert_eq!(body["enable_formula"], true);
        assert_eq!(body["enable_table"], false);
        assert_eq!(body["language"], "en");
        assert_eq!(body["data_id"], "abc-123");
        assert_eq!(body["page_ranges"], "1-10");
        assert_eq!(body["no_cache"], true);
        assert_eq!(body["cache_tolerance"], 600);
    }

    #[test]
    fn test_build_batch_submit_body() {
        let req = MinerUBatchSubmitRequest {
            files: vec![
                MinerUBatchFileEntry {
                    url: "https://example.com/a.pdf".into(),
                    data_id: Some("a".into()),
                    is_ocr: None,
                    page_ranges: None,
                },
                MinerUBatchFileEntry {
                    url: "https://example.com/b.pdf".into(),
                    data_id: None,
                    is_ocr: Some(true),
                    page_ranges: Some("1-5".into()),
                },
            ],
            model_version: Some("pipeline".into()),
            enable_formula: None,
            enable_table: None,
            language: None,
            no_cache: None,
            cache_tolerance: None,
        };
        let body = build_batch_submit_body(&req);
        let files = body["files"].as_array().unwrap();
        assert_eq!(files.len(), 2);
        assert_eq!(files[0]["url"], "https://example.com/a.pdf");
        assert_eq!(files[0]["data_id"], "a");
        assert_eq!(files[1]["is_ocr"], true);
        assert_eq!(files[1]["page_ranges"], "1-5");
        assert_eq!(body["model_version"], "pipeline");
    }

    #[test]
    fn test_create_task_body_html_model() {
        let req = MinerUCreateTaskRequest {
            url: "https://example.com/page.html".into(),
            model_version: Some("MinerU-HTML".into()),
            is_ocr: None,
            enable_formula: None,
            enable_table: None,
            language: None,
            data_id: None,
            page_ranges: None,
            no_cache: None,
            cache_tolerance: None,
        };
        let body = build_create_task_body(&req);
        assert_eq!(body["model_version"], "MinerU-HTML");
    }
}
```

**Step 2: Run tests to verify they fail**

```bash
cd backend/libs/http-io && cargo test --lib mineru
```

Expected: compilation errors because `HttpClient` doesn't have `post_json` / `get_json_with_auth` methods yet.

**Step 3: Add post_json and get_json_with_auth methods to client.rs**

Modify `backend/libs/http-io/src/client.rs` — add two new methods to `HttpClient`:

```rust
/// POST JSON with optional Authorization header.
pub async fn post_json(
    &self,
    url: &str,
    body: &serde_json::Value,
    auth_header: Option<&str>,
) -> Result<serde_json::Value, GatewayError> {
    let mut request = self
        .inner
        .post(url)
        .header("Content-Type", "application/json")
        .header("Accept", "*/*");

    if let Some(auth) = auth_header {
        request = request.header("Authorization", auth);
    }

    let response = request.json(body).send().await?;
    let json = response.error_for_status()?.json().await?;
    Ok(json)
}

/// GET with optional Authorization header, returning JSON.
pub async fn get_json_with_auth(
    &self,
    url: &str,
    auth_header: Option<&str>,
) -> Result<serde_json::Value, GatewayError> {
    let mut request = self.inner.get(url);

    if let Some(auth) = auth_header {
        request = request.header("Authorization", auth);
    }

    let response = request.send().await?;
    let json = response.error_for_status()?.json().await?;
    Ok(json)
}
```

**Step 4: Register mineru module in lib.rs**

Add `pub mod mineru;` to `backend/libs/http-io/src/lib.rs`:

```rust
pub mod client;
pub mod error;
pub mod mineru;
pub mod providers;
pub mod py;
pub mod scraper;
pub mod types;
```

**Step 5: Run tests**

```bash
cd backend/libs/http-io && cargo test --lib mineru
```

Expected: all 4 tests pass.

**Step 6: Commit**

```bash
git add backend/libs/http-io/src/mineru.rs backend/libs/http-io/src/client.rs backend/libs/http-io/src/lib.rs
git commit -m "feat: add MinerU API client module with request builders and tests"
```

---

### Task 7: Expose MinerU functions to Python via py.rs

**Files:**
- Modify: `backend/libs/http-io/src/py.rs`
- Modify: `backend/libs/rust-io/src/lib.rs`

**Step 1: Add MinerU Python functions to py.rs**

Append to `backend/libs/http-io/src/py.rs`:

```rust
// ── MinerU API functions ──────────────────────────────────────────────

#[pyfunction]
#[pyo3(signature = (url, token, model_version=None, is_ocr=None, enable_formula=None, enable_table=None, language=None, data_id=None, page_ranges=None, no_cache=None, cache_tolerance=None, timeout_ms=None, proxy=None))]
pub fn mineru_create_task<'py>(
    py: Python<'py>,
    url: String,
    token: String,
    model_version: Option<String>,
    is_ocr: Option<bool>,
    enable_formula: Option<bool>,
    enable_table: Option<bool>,
    language: Option<String>,
    data_id: Option<String>,
    page_ranges: Option<String>,
    no_cache: Option<bool>,
    cache_tolerance: Option<u32>,
    timeout_ms: Option<u64>,
    proxy: Option<String>,
) -> PyResult<Bound<'py, PyAny>> {
    let client = HttpClient::new(timeout_ms, None, proxy.as_deref())?;
    let request = crate::types::MinerUCreateTaskRequest {
        url,
        model_version,
        is_ocr,
        enable_formula,
        enable_table,
        language,
        data_id,
        page_ranges,
        no_cache,
        cache_tolerance,
    };

    pyo3_async_runtimes::tokio::future_into_py(py, async move {
        let result = crate::mineru::create_task(&client, &token, &request)
            .await
            .map_err(PyErr::from)?;
        Python::attach(|py| {
            pythonize::pythonize(py, &result)
                .map(|obj| obj.unbind())
                .map_err(PyErr::from)
        })
    })
}

#[pyfunction]
#[pyo3(signature = (task_id, token, timeout_ms=None, proxy=None))]
pub fn mineru_get_result<'py>(
    py: Python<'py>,
    task_id: String,
    token: String,
    timeout_ms: Option<u64>,
    proxy: Option<String>,
) -> PyResult<Bound<'py, PyAny>> {
    let client = HttpClient::new(timeout_ms, None, proxy.as_deref())?;

    pyo3_async_runtimes::tokio::future_into_py(py, async move {
        let result = crate::mineru::get_result(&client, &token, &task_id)
            .await
            .map_err(PyErr::from)?;
        Python::attach(|py| {
            pythonize::pythonize(py, &result)
                .map(|obj| obj.unbind())
                .map_err(PyErr::from)
        })
    })
}

#[pyfunction]
#[pyo3(signature = (files, token, model_version=None, enable_formula=None, enable_table=None, language=None, no_cache=None, cache_tolerance=None, timeout_ms=None, proxy=None))]
pub fn mineru_batch_submit<'py>(
    py: Python<'py>,
    files: Vec<Bound<'py, PyDict>>,
    token: String,
    model_version: Option<String>,
    enable_formula: Option<bool>,
    enable_table: Option<bool>,
    language: Option<String>,
    no_cache: Option<bool>,
    cache_tolerance: Option<u32>,
    timeout_ms: Option<u64>,
    proxy: Option<String>,
) -> PyResult<Bound<'py, PyAny>> {
    let client = HttpClient::new(timeout_ms, None, proxy.as_deref())?;

    let mut entries = Vec::with_capacity(files.len());
    for file_dict in &files {
        let url = file_dict
            .get_item("url")
            .map_err(py_err)?
            .ok_or_else(|| GatewayError::Other("file entry missing 'url'".into()))
            .and_then(|v| v.extract::<String>().map_err(|e| GatewayError::Other(e.to_string())))?;
        let data_id = file_dict
            .get_item("data_id")
            .map_err(py_err)?
            .map(|v| v.extract::<String>())
            .transpose()
            .map_err(py_err)?;
        let is_ocr = file_dict
            .get_item("is_ocr")
            .map_err(py_err)?
            .map(|v| v.extract::<bool>())
            .transpose()
            .map_err(py_err)?;
        let page_ranges = file_dict
            .get_item("page_ranges")
            .map_err(py_err)?
            .map(|v| v.extract::<String>())
            .transpose()
            .map_err(py_err)?;
        entries.push(crate::types::MinerUBatchFileEntry {
            url,
            data_id,
            is_ocr,
            page_ranges,
        });
    }

    let request = crate::types::MinerUBatchSubmitRequest {
        files: entries,
        model_version,
        enable_formula,
        enable_table,
        language,
        no_cache,
        cache_tolerance,
    };

    pyo3_async_runtimes::tokio::future_into_py(py, async move {
        let result = crate::mineru::batch_submit(&client, &token, &request)
            .await
            .map_err(PyErr::from)?;
        Python::attach(|py| {
            pythonize::pythonize(py, &result)
                .map(|obj| obj.unbind())
                .map_err(PyErr::from)
        })
    })
}

#[pyfunction]
#[pyo3(signature = (batch_id, token, timeout_ms=None, proxy=None))]
pub fn mineru_batch_result<'py>(
    py: Python<'py>,
    batch_id: String,
    token: String,
    timeout_ms: Option<u64>,
    proxy: Option<String>,
) -> PyResult<Bound<'py, PyAny>> {
    let client = HttpClient::new(timeout_ms, None, proxy.as_deref())?;

    pyo3_async_runtimes::tokio::future_into_py(py, async move {
        let result = crate::mineru::batch_result(&client, &token, &batch_id)
            .await
            .map_err(PyErr::from)?;
        Python::attach(|py| {
            pythonize::pythonize(py, &result)
                .map(|obj| obj.unbind())
                .map_err(PyErr::from)
        })
    })
}
```

**Step 2: Register MinerU functions in rust-io facade**

Modify `backend/libs/rust-io/src/lib.rs` — add MinerU function registrations to the `http` submodule:

```rust
http.add_function(wrap_pyfunction!(http_io::py::mineru_create_task, &http)?)?;
http.add_function(wrap_pyfunction!(http_io::py::mineru_get_result, &http)?)?;
http.add_function(wrap_pyfunction!(http_io::py::mineru_batch_submit, &http)?)?;
http.add_function(wrap_pyfunction!(http_io::py::mineru_batch_result, &http)?)?;
```

**Step 3: Verify compilation**

```bash
cd backend/libs/rust-io && cargo check
```

**Step 4: Commit**

```bash
git add backend/libs/http-io/src/py.rs backend/libs/rust-io/src/lib.rs
git commit -m "feat: expose MinerU API functions to Python via rust_io.http facade"
```

---

### Task 8: Build the extension and run full tests

**Files:**
- Test: all existing tests should still pass

**Step 1: Build the PyO3 extension**

```bash
cd backend && uv run maturin develop --release -m libs/rust-io/Cargo.toml
```

**Step 2: Run Rust tests for http-io**

```bash
cd backend/libs/http-io && cargo test
```

Expected: all tests pass (existing provider tests + new MinerU builder tests).

**Step 3: Run Python tests**

```bash
cd backend && uv run pytest tests/core/ingest_and_digitize_data/document_acquisition/online_acquisition/test_gateway.py -v
```

**Step 4: Verify Python import works**

```bash
cd backend && uv run python -c "import rust_io.http; print(dir(rust_io.http))"
```

Expected: output includes `fetch_one`, `fetch_multi`, `scrape_web`, `scrape_html`, `extract_pdf_links`, `mineru_create_task`, `mineru_get_result`, `mineru_batch_submit`, `mineru_batch_result`.

**Step 5: Commit (if any fixups needed)**

```bash
git add -A && git commit -m "chore: build extension and verify all tests pass"
```

---

### Task 9: Update AGENTS.md documentation

**Files:**
- Modify: `AGENTS.md`

**Step 1: Update Rust Native Extensions table**

Find the table that lists `literature-io` and update:

```markdown
| `http-io` | `rust_io.http` | Literature search/download via providers + MinerU document parsing API. Same provider set as rust-io, newer architecture. |
```

**Step 2: Commit**

```bash
git add AGENTS.md
git commit -m "docs: update AGENTS.md to reflect http-io rename and MinerU support"
```

---

## Verification Checklist

After all tasks:

- [ ] `backend/libs/http-io/` exists, `backend/libs/literature-io/` does not
- [ ] `cargo test` passes in `http-io` (all existing + MinerU tests)
- [ ] `cargo check` passes in `rust-io`
- [ ] `maturin develop --release` builds successfully
- [ ] `import rust_io.http` works in Python
- [ ] `rust_io.http.mineru_create_task` is callable
- [ ] `import rust_io.literature` raises ImportError (old name gone)
- [ ] Python gateway tests pass with updated imports
- [ ] No references to `literature-io` or `literature_io` remain in source code (only in docs/archive/)
