# net-io MinerU Local File Upload Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Status:** completed
**Created:** 2026-05-11
**Completed:** 2026-05-11
**Goal:** Add a MinerU local-file upload interface to `net-io` so Python callers can request MinerU upload URLs, upload local files, and receive the resulting batch task metadata.

**Architecture:** Keep `net-io` as the low-level HTTP client and expose new async PyO3 functions through the existing `rust_io.net` facade. Use MinerU API v4 `/file-urls/batch` for local files, then upload bytes to each returned pre-signed URL with `PUT`; MinerU auto-submits parsing after upload, so no extra task-submit API is called. Preserve existing URL-based single and batch parsing APIs.

**Tech Stack:** Rust 2024, reqwest, tokio, serde_json, PyO3 0.28, pyo3-async-runtimes, pytest facade regression tests, cargo tests.

---

## Context

### Current MinerU Surface

- `backend/libs/net-io/src/mineru.rs` implements:
  - `create_task()` → `POST /extract/task` for URL-based single-file parsing.
  - `get_result()` → `GET /extract/task/{task_id}`.
  - `batch_submit()` → `POST /extract/task/batch` for URL-based batch parsing.
  - `batch_result()` → `GET /extract-results/batch/{batch_id}`.
  - Existing helper code for a single upload URL may exist; verify before editing and avoid duplicating APIs.
- `backend/libs/net-io/src/py.rs` exposes Rust functions as async Python functions.
- `backend/libs/rust-io/src/lib.rs` registers `net_io::py::*` functions under `rust_io.net`.
- `backend/tests/core/ingest_and_digitize_data/test_rust_io_facade.py` verifies Python facade exports.

### MinerU API Behavior Required

From the provided MinerU v4 docs:

- Endpoint: `POST https://mineru.net/api/v4/file-urls/batch`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <token>`
- Request body shape:

```json
{
  "files": [
    {"name": "demo.pdf", "data_id": "abcd"}
  ],
  "model_version": "vlm"
}
```

- Optional body fields:
  - Top-level: `model_version`, `enable_formula`, `enable_table`, `language`, `callback`, `seed`, `extra_formats`
  - Per file: `name`, `data_id`, `is_ocr`, `page_ranges`
- Response shape:

```json
{
  "code": 0,
  "data": {
    "batch_id": "2bb2f0ec-a336-4a0a-b61a-241afaf9cc87",
    "file_urls": ["https://***"]
  },
  "msg": "ok",
  "trace_id": "c876cd60b202f2396de1f9e39a1b0172"
}
```

- Upload each local file with `PUT <file_url>` and raw file bytes.
- MinerU docs say no `Content-Type` header is required for the upload `PUT`; do not add one in the new combined upload path.
- After upload completes, MinerU automatically submits parsing tasks. Return the original batch response so callers can use `data.batch_id` with `mineru_batch_result()`.

### Non-Goals

- Do not change existing URL-based MinerU functions.
- Do not add Python business-layer parsing changes in `backend/src/core/...` in this plan.
- Do not add retries or polling semantics beyond the existing `HttpClient` behavior.
- Do not introduce mocks for Rust unit tests; test pure body-building logic directly.

---

## Task 1: Add request types for local upload batches

**Files:**
- Modify: `backend/libs/net-io/src/types.rs`

**Step 1: Write the failing compile-time usage**

Add tests first in Task 2 before implementing these types. The failing tests should reference the new types:

```rust
MinerULocalFileEntry
MinerUBatchUploadUrlRequest
```

Expected initial failure: Rust compiler reports the types are not found.

**Step 2: Add the minimal types**

In `backend/libs/net-io/src/types.rs`, after `MinerUBatchSubmitRequest`, add:

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MinerULocalFileEntry {
    pub name: String,
    pub data_id: Option<String>,
    pub is_ocr: Option<bool>,
    pub page_ranges: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MinerUBatchUploadUrlRequest {
    pub files: Vec<MinerULocalFileEntry>,
    pub model_version: Option<String>,
    pub enable_formula: Option<bool>,
    pub enable_table: Option<bool>,
    pub language: Option<String>,
    pub callback: Option<String>,
    pub seed: Option<String>,
    pub extra_formats: Option<Vec<String>>,
}
```

**Step 3: Format**

Run:

```bash
cd backend/libs/net-io && cargo fmt
```

Expected: no output.

**Step 4: Commit**

```bash
git add backend/libs/net-io/src/types.rs
git commit -m "feat: add mineru local upload request types"
```

---

## Task 2: Add local upload request body tests

**Files:**
- Modify: `backend/libs/net-io/src/mineru.rs`

**Step 1: Write failing tests**

In `backend/libs/net-io/src/mineru.rs`, inside `#[cfg(test)] mod tests`, update imports:

```rust
use crate::types::{MinerUBatchFileEntry, MinerUBatchUploadUrlRequest, MinerULocalFileEntry};
```

Add these tests:

```rust
#[test]
fn test_build_batch_upload_url_body() {
    let req = MinerUBatchUploadUrlRequest {
        files: vec![
            MinerULocalFileEntry {
                name: "paper.pdf".into(),
                data_id: Some("paper-1".into()),
                is_ocr: None,
                page_ranges: None,
            },
            MinerULocalFileEntry {
                name: "table.xlsx".into(),
                data_id: None,
                is_ocr: Some(true),
                page_ranges: Some("1-2".into()),
            },
        ],
        model_version: Some("vlm".into()),
        enable_formula: Some(true),
        enable_table: Some(false),
        language: Some("en".into()),
        callback: Some("https://example.com/callback".into()),
        seed: Some("seed_1".into()),
        extra_formats: Some(vec!["docx".into(), "html".into()]),
    };

    let body = build_batch_upload_url_body(&req);

    let files = body["files"].as_array().unwrap();
    assert_eq!(files.len(), 2);
    assert_eq!(files[0]["name"], "paper.pdf");
    assert_eq!(files[0]["data_id"], "paper-1");
    assert!(files[0].get("is_ocr").is_none());
    assert_eq!(files[1]["name"], "table.xlsx");
    assert_eq!(files[1]["is_ocr"], true);
    assert_eq!(files[1]["page_ranges"], "1-2");
    assert_eq!(body["model_version"], "vlm");
    assert_eq!(body["enable_formula"], true);
    assert_eq!(body["enable_table"], false);
    assert_eq!(body["language"], "en");
    assert_eq!(body["callback"], "https://example.com/callback");
    assert_eq!(body["seed"], "seed_1");
    assert_eq!(body["extra_formats"], serde_json::json!(["docx", "html"]));
}

#[test]
fn test_build_batch_upload_url_body_omits_unset_options() {
    let req = MinerUBatchUploadUrlRequest {
        files: vec![MinerULocalFileEntry {
            name: "demo.html".into(),
            data_id: None,
            is_ocr: None,
            page_ranges: None,
        }],
        model_version: Some("MinerU-HTML".into()),
        enable_formula: None,
        enable_table: None,
        language: None,
        callback: None,
        seed: None,
        extra_formats: None,
    };

    let body = build_batch_upload_url_body(&req);

    assert_eq!(body["files"][0]["name"], "demo.html");
    assert_eq!(body["model_version"], "MinerU-HTML");
    assert!(body.get("enable_formula").is_none());
    assert!(body.get("callback").is_none());
    assert!(body.get("extra_formats").is_none());
}
```

**Step 2: Run tests to verify failure**

Run:

```bash
cd backend/libs/net-io && cargo test test_build_batch_upload_url_body
```

Expected: FAIL with compiler error similar to:

```text
cannot find function `build_batch_upload_url_body` in this scope
```

**Step 3: Commit failing test**

```bash
git add backend/libs/net-io/src/mineru.rs
git commit -m "test: cover mineru local upload request body"
```

---

## Task 3: Implement MinerU batch upload URL creation

**Files:**
- Modify: `backend/libs/net-io/src/mineru.rs`

**Step 1: Import new types**

At the top of `mineru.rs`, update the type import to include local upload types:

```rust
use crate::types::{
    MinerUBatchSubmitRequest, MinerUBatchUploadUrlRequest, MinerUCreateTaskRequest,
    MinerULocalFileEntry, MinerUUploadUrlRequest,
};
```

**Step 2: Add public API function**

After existing `create_upload_url()` or near other upload functions, add:

```rust
/// Get pre-signed upload URLs for local files. Uploaded files are auto-submitted by MinerU.
/// POST /file-urls/batch
pub async fn create_batch_upload_urls(
    client: &HttpClient,
    token: &str,
    request: &MinerUBatchUploadUrlRequest,
) -> Result<Value, GatewayError> {
    let url = format!("{MINERU_BASE_URL}/file-urls/batch");
    let body = build_batch_upload_url_body(request);
    post_json_with_auth(client, &url, token, &body).await
}
```

**Step 3: Add request-body helpers**

Near the existing body-builder helpers, add:

```rust
fn build_batch_upload_url_body(request: &MinerUBatchUploadUrlRequest) -> Value {
    let files: Vec<Value> = request
        .files
        .iter()
        .map(build_local_file_entry)
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
    if let Some(ref v) = request.callback {
        body["callback"] = Value::String(v.clone());
    }
    if let Some(ref v) = request.seed {
        body["seed"] = Value::String(v.clone());
    }
    if let Some(ref v) = request.extra_formats {
        body["extra_formats"] = serde_json::json!(v);
    }
    body
}

fn build_local_file_entry(file: &MinerULocalFileEntry) -> Value {
    let mut entry = serde_json::json!({ "name": file.name });
    if let Some(ref v) = file.data_id {
        entry["data_id"] = Value::String(v.clone());
    }
    if let Some(v) = file.is_ocr {
        entry["is_ocr"] = Value::Bool(v);
    }
    if let Some(ref v) = file.page_ranges {
        entry["page_ranges"] = Value::String(v.clone());
    }
    entry
}
```

**Step 4: Run tests to verify pass**

Run:

```bash
cd backend/libs/net-io && cargo test test_build_batch_upload_url_body
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/libs/net-io/src/mineru.rs
git commit -m "feat: create mineru local upload urls"
```

---

## Task 4: Add combined create-and-upload function

**Files:**
- Modify: `backend/libs/net-io/src/mineru.rs`

**Step 1: Write failing test for response validation helper**

Do not make a network test. Extract only the URL extraction/validation logic into a pure helper.

Add this helper test first:

```rust
#[test]
fn test_extract_upload_urls_rejects_missing_file_urls() {
    let response = serde_json::json!({"code": 0, "data": {"batch_id": "batch-1"}});

    let err = extract_upload_urls(&response).unwrap_err();

    assert!(err.to_string().contains("missing data.file_urls"));
}

#[test]
fn test_extract_upload_urls_returns_urls() {
    let response = serde_json::json!({
        "code": 0,
        "data": {"file_urls": ["https://upload-1", "https://upload-2"]}
    });

    let urls = extract_upload_urls(&response).unwrap();

    assert_eq!(urls, vec!["https://upload-1".to_string(), "https://upload-2".to_string()]);
}
```

**Step 2: Run tests to verify failure**

Run:

```bash
cd backend/libs/net-io && cargo test extract_upload_urls
```

Expected: FAIL with `cannot find function extract_upload_urls`.

**Step 3: Add pure helper**

Add:

```rust
fn extract_upload_urls(response: &Value) -> Result<Vec<String>, GatewayError> {
    response
        .get("data")
        .and_then(|data| data.get("file_urls"))
        .and_then(|value| value.as_array())
        .ok_or_else(|| GatewayError::Other("MinerU upload URL response missing data.file_urls".into()))?
        .iter()
        .map(|value| {
            value
                .as_str()
                .map(str::to_owned)
                .ok_or_else(|| GatewayError::Other("MinerU upload URL is not a string".into()))
        })
        .collect()
}
```

**Step 4: Add combined upload function**

Add:

```rust
/// Create upload URLs and upload local files. MinerU auto-submits parsing after upload.
pub async fn upload_local_files(
    client: &HttpClient,
    token: &str,
    request: &MinerUBatchUploadUrlRequest,
    file_paths: &[String],
) -> Result<Value, GatewayError> {
    let response = create_batch_upload_urls(client, token, request).await?;
    let urls = extract_upload_urls(&response)?;

    if urls.len() != file_paths.len() {
        return Err(GatewayError::Other(format!(
            "MinerU returned {} upload URLs for {} local files",
            urls.len(),
            file_paths.len()
        )));
    }

    for (upload_url, file_path) in urls.iter().zip(file_paths) {
        upload_local_file(client, upload_url, file_path, None).await?;
    }

    Ok(response)
}
```

**Step 5: Run tests**

Run:

```bash
cd backend/libs/net-io && cargo test extract_upload_urls
cd backend/libs/net-io && cargo test
```

Expected: all `net-io` tests pass.

**Step 6: Commit**

```bash
git add backend/libs/net-io/src/mineru.rs
git commit -m "feat: upload mineru local files"
```

---

## Task 5: Add PyO3 wrappers for local upload APIs

**Files:**
- Modify: `backend/libs/net-io/src/py.rs`

**Step 1: Add `mineru_create_batch_upload_urls` wrapper**

Add after `mineru_create_upload_url()`:

```rust
#[pyfunction]
#[pyo3(signature = (files, token, model_version=None, enable_formula=None, enable_table=None, language=None, callback=None, seed=None, extra_formats=None, timeout_ms=None, proxy=None))]
pub fn mineru_create_batch_upload_urls<'py>(
    py: Python<'py>,
    files: Vec<Bound<'py, PyDict>>,
    token: String,
    model_version: Option<String>,
    enable_formula: Option<bool>,
    enable_table: Option<bool>,
    language: Option<String>,
    callback: Option<String>,
    seed: Option<String>,
    extra_formats: Option<Vec<String>>,
    timeout_ms: Option<u64>,
    proxy: Option<String>,
) -> PyResult<Bound<'py, PyAny>> {
    let client = HttpClient::new(timeout_ms, None, proxy.as_deref())?;

    let mut entries = Vec::with_capacity(files.len());
    for file_dict in &files {
        let name = file_dict
            .get_item("name")
            .map_err(py_err)?
            .ok_or_else(|| GatewayError::Other("file entry missing 'name'".into()))
            .and_then(|v| {
                v.extract::<String>()
                    .map_err(|e| GatewayError::Other(e.to_string()))
            })?;
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
        entries.push(crate::types::MinerULocalFileEntry {
            name,
            data_id,
            is_ocr,
            page_ranges,
        });
    }

    let request = crate::types::MinerUBatchUploadUrlRequest {
        files: entries,
        model_version,
        enable_formula,
        enable_table,
        language,
        callback,
        seed,
        extra_formats,
    };

    pyo3_async_runtimes::tokio::future_into_py(py, async move {
        let result = crate::mineru::create_batch_upload_urls(&client, &token, &request)
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

**Step 2: Add `mineru_upload_local_files` wrapper**

Add before the single-file `mineru_upload_local_file()` wrapper:

```rust
#[pyfunction]
#[pyo3(signature = (file_paths, token, model_version=None, enable_formula=None, enable_table=None, language=None, data_ids=None, is_ocr=None, page_ranges=None, callback=None, seed=None, extra_formats=None, timeout_ms=None, proxy=None))]
pub fn mineru_upload_local_files<'py>(
    py: Python<'py>,
    file_paths: Vec<String>,
    token: String,
    model_version: Option<String>,
    enable_formula: Option<bool>,
    enable_table: Option<bool>,
    language: Option<String>,
    data_ids: Option<Vec<String>>,
    is_ocr: Option<bool>,
    page_ranges: Option<String>,
    callback: Option<String>,
    seed: Option<String>,
    extra_formats: Option<Vec<String>>,
    timeout_ms: Option<u64>,
    proxy: Option<String>,
) -> PyResult<Bound<'py, PyAny>> {
    let client = HttpClient::new(timeout_ms, None, proxy.as_deref())?;
    if let Some(ref ids) = data_ids {
        if ids.len() != file_paths.len() {
            return Err(PyErr::from(GatewayError::Other(format!(
                "data_ids length {} does not match file_paths length {}",
                ids.len(),
                file_paths.len()
            ))));
        }
    }

    let entries = file_paths
        .iter()
        .enumerate()
        .map(|(idx, path)| {
            let name = std::path::Path::new(path)
                .file_name()
                .and_then(|value| value.to_str())
                .ok_or_else(|| GatewayError::Other(format!("local file path has no valid filename: {path}")))?
                .to_owned();
            let data_id = data_ids.as_ref().map(|ids| ids[idx].clone());
            Ok(crate::types::MinerULocalFileEntry {
                name,
                data_id,
                is_ocr,
                page_ranges: page_ranges.clone(),
            })
        })
        .collect::<Result<Vec<_>, GatewayError>>()?;

    let request = crate::types::MinerUBatchUploadUrlRequest {
        files: entries,
        model_version,
        enable_formula,
        enable_table,
        language,
        callback,
        seed,
        extra_formats,
    };

    pyo3_async_runtimes::tokio::future_into_py(py, async move {
        let result = crate::mineru::upload_local_files(&client, &token, &request, &file_paths)
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

**Step 3: Format and compile**

Run:

```bash
cd backend/libs/net-io && cargo fmt
cd backend/libs/net-io && cargo test
```

Expected: all tests pass.

**Step 4: Commit**

```bash
git add backend/libs/net-io/src/py.rs
git commit -m "feat: expose mineru local upload wrappers"
```

---

## Task 6: Register facade exports

**Files:**
- Modify: `backend/libs/rust-io/src/lib.rs`
- Modify: `backend/tests/core/ingest_and_digitize_data/test_rust_io_facade.py`

**Step 1: Write failing facade test**

In `test_net_io_facade_exports_provider_functions`, add these names to the tuple:

```python
"mineru_create_upload_url",
"mineru_create_batch_upload_urls",
"mineru_upload_local_file",
"mineru_upload_local_files",
```

Run:

```bash
cd backend && uv run pytest tests/core/ingest_and_digitize_data/test_rust_io_facade.py::test_net_io_facade_exports_provider_functions -q
```

Expected before registration/rebuild: FAIL because one or more attributes are missing.

**Step 2: Register functions in facade**

In `backend/libs/rust-io/src/lib.rs`, under the other MinerU registrations, add:

```rust
net.add_function(wrap_pyfunction!(
    net_io::py::mineru_create_upload_url,
    &net
)?)?;
net.add_function(wrap_pyfunction!(
    net_io::py::mineru_create_batch_upload_urls,
    &net
)?)?;
net.add_function(wrap_pyfunction!(
    net_io::py::mineru_upload_local_file,
    &net
)?)?;
net.add_function(wrap_pyfunction!(
    net_io::py::mineru_upload_local_files,
    &net
)?)?;
```

**Step 3: Compile Rust facade**

Run:

```bash
cd backend/libs/rust-io && cargo test
```

Expected: PASS.

**Step 4: Rebuild editable Python extension**

Run:

```bash
cd backend && uv run maturin develop --release -m libs/rust-io/Cargo.toml
```

Expected: wheel builds and installs. A warning about missing `patchelf` is acceptable if the extension imports successfully afterward.

**Step 5: Run facade test again**

Run:

```bash
cd backend && uv run pytest tests/core/ingest_and_digitize_data/test_rust_io_facade.py::test_net_io_facade_exports_provider_functions -q
```

Expected: PASS.

**Step 6: Commit**

```bash
git add backend/libs/rust-io/src/lib.rs backend/tests/core/ingest_and_digitize_data/test_rust_io_facade.py
git commit -m "feat: export mineru local upload facade"
```

---

## Task 7: Document Python API usage

**Files:**
- Modify: `backend/libs/net-io/README.md`
- Modify: `backend/libs/rust-io/README.md`

**Step 1: Update `backend/libs/net-io/README.md` MinerU API section**

Add these signatures under `### MinerU Document Parsing`:

```python
async def mineru_create_batch_upload_urls(
    files: list[dict],                     # each: {"name": str, "data_id"?, "is_ocr"?, "page_ranges"?}
    token: str,
    model_version: str | None = None,
    enable_formula: bool | None = None,
    enable_table: bool | None = None,
    language: str | None = None,
    callback: str | None = None,
    seed: str | None = None,               # required by MinerU when callback is set
    extra_formats: list[str] | None = None, # MinerU supports: "docx", "html", "latex"
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
) -> dict
```

Add usage example:

```python
import rust_io.net as net_io

batch = await net_io.mineru_upload_local_files(
    ["/tmp/demo.pdf"],
    token="your_mineru_token",
    model_version="vlm",
    language="en",
    data_ids=["demo-1"],
)

batch_id = batch["data"]["batch_id"]
result = await net_io.mineru_batch_result(batch_id, token="your_mineru_token")
```

**Step 2: Update `backend/libs/rust-io/README.md` facade table**

Add rows for:

```markdown
| `mineru_create_upload_url` | `(filename, token, content_type=None, model_version=None, is_ocr=None, enable_formula=None, enable_table=None, language=None, data_id=None, page_ranges=None, no_cache=None, cache_tolerance=None, timeout_ms=None, proxy=None) -> dict` | Get a pre-signed upload URL for a local file. |
| `mineru_create_batch_upload_urls` | `(files, token, model_version=None, enable_formula=None, enable_table=None, language=None, callback=None, seed=None, extra_formats=None, timeout_ms=None, proxy=None) -> dict` | Get pre-signed upload URLs for multiple local files. |
| `mineru_upload_local_file` | `(upload_url, file_path, content_type=None, timeout_ms=None, proxy=None) -> dict` | Upload one local file to a pre-signed URL. |
| `mineru_upload_local_files` | `(file_paths, token, model_version=None, enable_formula=None, enable_table=None, language=None, data_ids=None, is_ocr=None, page_ranges=None, callback=None, seed=None, extra_formats=None, timeout_ms=None, proxy=None) -> dict` | Create upload URLs and upload local files; MinerU auto-submits parsing after upload. |
```

**Step 3: Review docs only**

Run:

```bash
git diff -- backend/libs/net-io/README.md backend/libs/rust-io/README.md
```

Expected: docs mention the local upload URL flow and do not claim local parsing is synchronous.

**Step 4: Commit**

```bash
git add backend/libs/net-io/README.md backend/libs/rust-io/README.md
git commit -m "docs: document mineru local upload APIs"
```

---

## Task 8: Final verification

**Files:**
- No code changes expected.

**Step 1: Run Rust crate tests**

```bash
cd backend/libs/net-io && cargo test
cd backend/libs/rust-io && cargo test
```

Expected:

```text
net-io: all tests pass
rust-io: all tests pass
```

**Step 2: Rebuild Python extension**

```bash
cd backend && uv run maturin develop --release -m libs/rust-io/Cargo.toml
```

Expected: install succeeds.

**Step 3: Run facade regression**

```bash
cd backend && uv run pytest tests/core/ingest_and_digitize_data/test_rust_io_facade.py -q
```

Expected: all facade tests pass.

**Step 4: Manually inspect Python API names**

```bash
cd backend && uv run python - <<'PY'
import rust_io.net as net_io
print(sorted(name for name in dir(net_io) if name.startswith("mineru_")))
PY
```

Expected output includes:

```text
mineru_batch_result
mineru_batch_submit
mineru_create_batch_upload_urls
mineru_create_task
mineru_create_upload_url
mineru_get_result
mineru_upload_local_file
mineru_upload_local_files
```

**Step 5: Update progress log**

Append to root `progress.txt`:

```text
[2026-05-11] [Planned net-io MinerU local file upload API] [completed]
```

**Step 6: Commit verification/progress**

```bash
git add progress.txt
git commit -m "chore: record mineru local upload planning"
```

---

## Acceptance Criteria

- `net-io` has typed request structs for local upload URL requests.
- `net-io::mineru::create_batch_upload_urls()` calls MinerU `/file-urls/batch` with the documented body shape.
- `net-io::mineru::upload_local_files()` uploads raw local file bytes to returned URLs and returns the original batch response.
- `rust_io.net` exposes:
  - `mineru_create_upload_url`
  - `mineru_create_batch_upload_urls`
  - `mineru_upload_local_file`
  - `mineru_upload_local_files`
- README docs explain that MinerU auto-submits parsing after local upload.
- `cargo test` passes for `backend/libs/net-io` and `backend/libs/rust-io`.
- `uv run pytest tests/core/ingest_and_digitize_data/test_rust_io_facade.py -q` passes after rebuilding the extension.

## Rollback Plan

If the new facade breaks import or registration:

1. Revert only the new registrations in `backend/libs/rust-io/src/lib.rs`.
2. Keep pure Rust body-builder tests if they pass; they are isolated and safe.
3. Rebuild with `uv run maturin develop --release -m libs/rust-io/Cargo.toml`.
4. Re-run `uv run pytest tests/core/ingest_and_digitize_data/test_rust_io_facade.py -q`.

Do not remove existing URL-based MinerU functions during rollback.
