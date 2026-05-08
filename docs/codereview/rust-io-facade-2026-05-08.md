# Code Review: refactor/rust-io-facade

- **Branch**: `refactor/rust-io-facade`
- **Date**: 2026-05-08
- **Reviewer**: Sisyphus (AI)
- **Scope**: 9 commits, 27 files changed (+151 / -87)
- **Pass**: Second (deep line-by-line of all files)

---

## 1. Overview

This branch refactors the monolithic `rust-io` crate into a 3-crate facade architecture:

| Crate | Role | Crate Type |
|-------|------|------------|
| `rust-io` | Thin PyO3 facade, registers submodules | `cdylib` + `rlib` |
| `files-io` | File I/O, S3, archives, dedup | `rlib` only |
| `literature-io` | Literature acquisition (7 providers, HTTP client, scraper) | `rlib` only |

**Dependency graph**:
```
rust-io (cdylib) ──┬── files-io (rlib)
                   └── literature-io (rlib)
```

**Python migration**: All imports changed from `files_io` / `literature_io` to `rust_io.files` / `rust_io.literature`.

---

## 2. Verification Results

| Check | Result |
|-------|--------|
| `cargo check` (rust-io workspace) | ✅ Clean |
| `cargo test -p literature-io` | ✅ 10/10 passed |
| `cargo test -p files-io` | ✅ 1/1 passed |
| `cargo test -p rust-io` | ✅ 0 tests (compiles) |
| `unsafe` blocks | ✅ None found (grep hits are string literals) |
| Python import migration | ✅ All 3 service files migrated |
| Facade test (`test_rust_io_facade.py`) | ✅ Covers both submodules |

---

## 3. Findings

### 🔴 [blocking] Must Fix Before Merge

#### 3.1 Dead test file imports removed crate as Python module

**File**: `backend/libs/files-io/tests/test_files_io.py` line 6

```python
import files_io  # ← BROKEN: files-io is now rlib-only, not importable as Python module
```

`files-io` no longer has a `#[pymodule]` entry point. This test **will fail** when run.

**Fix**: Delete this file (the facade test `test_rust_io_facade.py` already covers the same surface via `rust_io.files`), or migrate it to `import rust_io.files as files_io`.

---

### 🟡 [important] Should Fix, Discuss if Disagree

#### 3.2 S3 backend uses `block_on()` — potential deadlock in async context

**File**: `backend/libs/files-io/src/backends/s3.rs:71-87`

```rust
fn read_all(&self, path: &str) -> Result<Vec<u8>, FileError> {
    let (bucket, key) = parse_s3_path(path)?;
    let resp = self.rt().block_on(          // ← blocks the calling thread
        self.client.get_object().bucket(bucket).key(key).send()
    ).map_err(|e| FileError::S3(e.to_string()))?;
    let bytes = self.rt().block_on(resp.body.collect())
        .map_err(|e| FileError::S3(e.to_string()))?;
    Ok(bytes.to_vec())
}
```

Every `FileOps` method uses `self.rt().block_on()` to bridge sync→async. This is **correct** when called from Python's synchronous context. However:

- If called from within a tokio runtime (e.g., from `batch_copy_async` which uses `spawn_blocking`), the `block_on` runs on a **separate** runtime (`S3_RT`), so it won't deadlock with the main runtime. This is safe.
- But it means **every S3 operation creates its own blocking segment** — no request pipelining within a single `File` method.

**Recommendation**: Document this design decision. Consider adding an `async fn read_all_async()` method to the trait for the async-native path.

#### 3.3 `S3Backend` accesses `is_truncated` as raw field

**File**: `backend/libs/files-io/src/backends/s3.rs:204,242`

```rust
if resp.is_truncated.unwrap_or(false) {
```

The AWS SDK provides `is_truncated()` method. Accessing the raw field may break on SDK updates. Use:

```rust
if resp.is_truncated().unwrap_or(false) {
```

#### 3.4 Zip extraction: symlink escape not checked

**File**: `backend/libs/files-io/src/archive/zip.rs:50-78`

The path traversal guard checks for `..` and `/` components, but does **not** check if a previously-extracted entry created a symlink that points outside `output_dir`. A malicious zip could:

1. Create a symlink `foo -> /etc`
2. Create a file `foo/passwd` with malicious content

The `tar_gz` extraction has the same pattern. Consider:
- Rejecting entries that are symlinks, or
- Verifying the final resolved path stays within `output_dir` after following symlinks

#### 3.5 `HttpClient::default()` panics on failure

**File**: `backend/libs/literature-io/src/client.rs:96-99`

```rust
impl Default for HttpClient {
    fn default() -> Self {
        Self::new(None, None, None).unwrap()  // ← panics if Client::builder().build() fails
    }
}
```

A `Default` impl shouldn't panic. Options:
- Remove `Default` impl entirely (callers should use `new()` explicitly)
- Or use `expect("default HTTP client should always build")` with a descriptive message

#### 3.6 `fetch_multi` executes providers sequentially

**File**: `backend/libs/literature-io/src/py.rs:53-61`

```rust
for provider in providers {
    results.push(
        execute_provider(&client, &provider, &action, &params)
            .await
            .map_err(PyErr::from)?,  // ← sequential, first failure aborts all
    );
}
```

For a multi-provider search, Provider B doesn't start until A finishes. Consider `futures::join_all` or `tokio::JoinSet` for parallelism. At minimum, collect errors instead of short-circuiting on first failure.

#### 3.7 Hardcoded fallback email for Unpaywall

**File**: `backend/libs/literature-io/src/providers/unpaywall.rs:17`

```rust
let email = std::env::var("UNPAYWALL_EMAIL").unwrap_or_else(|_| "test@example.com".into());
```

`"test@example.com"` may violate Unpaywall's API terms. This should be:
- A required config parameter (fail if missing), or
- Documented as a known limitation

#### 3.8 DOIs not URL-encoded in Crossref/OpenAlex providers

**File**: `backend/libs/literature-io/src/providers/crossref.rs:18`

```rust
let url = format!("https://api.crossref.org/works/{}", doi);
```

**File**: `backend/libs/literature-io/src/providers/openalex.rs:19`

```rust
let filter = format!("doi:{}", doi);
```

DOIs can contain special characters (e.g., `10.1002/(SICI)1097-0258(19980815)17:15<1661::AID-SIM889>3.0.CO;2-2`). These should be URL-encoded:

```rust
let url = format!("https://api.crossref.org/works/{}", urlencoding::encode(doi));
```

The `unpaywall.rs` provider correctly uses `urlencoding::encode(doi)` — follow the same pattern.

#### 3.9 Exponential backoff overflow risk

**File**: `backend/libs/literature-io/src/client.rs:58`

```rust
let backoff = Duration::from_millis(BACKOFF_BASE_MS * (1 << (attempt - 1)));
```

With `attempt: u32`, `1 << 31` would overflow `u64` multiplication. In practice `max_retries` is small, but adding a saturating clamp would be defensive:

```rust
let shift = (attempt - 1).min(20);  // cap at ~1M ms
let backoff = Duration::from_millis(BACKOFF_BASE_MS * (1u64 << shift));
```

#### 3.10 Error type information lost in Python boundary

**File**: `backend/libs/literature-io/src/error.rs:21-24`

```rust
impl From<GatewayError> for pyo3::PyErr {
    fn from(err: GatewayError) -> Self {
        pyo3::exceptions::PyRuntimeError::new_err(err.to_string())  // ← all errors become RuntimeError
    }
}
```

Python callers can't distinguish HTTP errors from JSON parse errors from provider errors. Consider mapping to different Python exception types:

| Rust variant | Python exception |
|-------------|-----------------|
| `GatewayError::Http` | `ConnectionError` |
| `GatewayError::Json` | `ValueError` |
| `GatewayError::Url` | `ValueError` |
| `GatewayError::Provider` | `RuntimeError` |
| `GatewayError::Other` | `RuntimeError` |

Same issue exists in `files-io/src/error.rs:30-33` — all `FileError` variants map to `PyRuntimeError`.

---

### 🟢 [nit] Nice to Have, Not Blocking

#### 3.11 Unused parameters in `scrape_provider`

**File**: `backend/libs/literature-io/src/scraper.rs:79-85`

```rust
pub async fn scrape_provider(
    client: &HttpClient,
    provider: &str,   // ← unused
    action: &Action,   // ← unused
    params: &FetchParams,
) -> Result<FetchResult, GatewayError> {
    let _ = (provider, action);  // ← explicit silence
```

This suggests the function is a stub. If it's meant to dispatch by provider, it should do so. If not, consider renaming to `scrape_url` and removing the unused params.

#### 3.12 O(n²) dedup in `extract_pdf_links`

**File**: `backend/libs/literature-io/src/scraper.rs:57`

```rust
if !links.contains(&absolute) {  // ← O(n) per check
    links.push(absolute);
}
```

For PDF links on a typical page (<20), this is negligible. For correctness, `HashSet` would be cleaner, but not blocking.

#### 3.13 PMC provider: redundant two-step lookup for PMCID

**File**: `backend/libs/literature-io/src/providers/pmc.rs:69-107`

`fetch_by_pmcid()` strips the `PMC` prefix, then searches `esearch` with `format!("{}[uid]", clean_id)`. PMC eutils supports direct PMC ID lookup — consider using `id:PMC12345[uid]` format directly, or the `elink` endpoint for PMID→PMCID conversion.

#### 3.14 EuropePMC: deeply nested identifier priority logic

**File**: `backend/libs/literature-io/src/providers/europepmc.rs:17-41`

The DOI→PMID→query fallback logic is 25 lines of nested `if let`. This could be simplified:

```rust
let search_query = params.identifiers.as_ref()
    .and_then(|ids| {
        ids.doi.as_deref().filter(|s| !s.is_empty()).map(|d| format!("DOI:{d}"))
            .or_else(|| ids.pmid.as_deref().filter(|s| !s.is_empty()).map(|p| format!("EXT_ID:{p}")))
    })
    .unwrap_or_else(|| query.to_string());
```

#### 3.15 `pyo3` dependency in rlib-only crates

Both `files-io` and `literature-io` depend on `pyo3` despite being rlib-only. This is **correct** — they use `#[pyfunction]`/`#[pyclass]` attributes which require the pyo3 crate. The `extension-module` feature is correctly omitted (only in `rust-io`'s Cargo.toml).

---

## 4. Architecture Assessment

### Facade Registration

The `register_submodule()` function correctly:
1. Creates a new `PyModule` with a short name (`"files"`, `"literature"`)
2. Adds it as a submodule to the parent (`m.add_submodule()`)
3. Registers it in `sys.modules` with the fully qualified name (`"rust_io.files"`, `"rust_io.literature"`)

This enables both import styles:
```python
import rust_io.files                    # works
from rust_io.files import File         # works
import rust_io.files as files_io       # works (used in service files)
```

### Module Visibility

Both sub-crates correctly expose all `py` submodule items as `pub`:

- `files-io`: `pub mod py` → `pub mod file`, `pub mod parallel`, `pub mod dedup`, `pub mod utils`
- `literature-io`: `pub mod py` → all `#[pyfunction]`s are `pub`

The facade (`rust-io`) references these via `files_io::py::file::File`, `literature_io::py::fetch_one`, etc.

### Python Import Migration

All 3 service files correctly migrated:

| File | Old import | New import |
|------|-----------|------------|
| `gateway.py:197` | `import literature_io` | `import rust_io.literature as literature_io` |
| `base.py:40,63` | `import literature_io` | `import rust_io.literature as literature_io` |
| `service.py:21` | `import files_io` | `import rust_io.files as files_io` |

All maintain graceful fallback on `ImportError`.

### Error Handling Pattern

Both crates use `thiserror` for structured error types with `#[source]` for error chain preservation. Both implement `From<XxxError> for pyo3::PyErr` for Python boundary crossing. The pattern is consistent but loses type information (see 3.10).

---

## 5. Test Coverage

### Rust Tests

| Crate | Tests | Coverage |
|-------|-------|----------|
| `literature-io` | 10 | Scraper: HTML parsing, CSS selectors, PDF link extraction, relative URL resolution, dedup |
| `files-io` | 1 | Compatibility: `compute_sha256`, `write_file`, `validate_pdf_magic` match legacy behavior |
| `rust-io` | 0 | (facade only, tested via Python) |

### Python Tests

| File | Tests | Coverage |
|------|-------|----------|
| `test_rust_io_facade.py` | 3 | Literature facade exports (5 functions), files facade legacy helpers (3 functions), files facade exports (6 items) |

### Gaps

- No integration test for `fetch_one` / `fetch_multi` / `scrape_web` (requires network or mock)
- No test for `File` class operations via `rust_io.files` (exists in dead `test_files_io.py`)
- No test for error handling / Python exception mapping
- No test for S3 backend (requires mock or LocalStack)
- No test for archive extraction path traversal guard

---

## 6. Decision

🔄 **Request Changes** — 1 blocking issue (dead test file), plus several important items to address.

The architecture is sound. The blocking item is a quick fix. The important items (sequential fetch, error type mapping, DOI encoding, symlink escape) are worth addressing for production quality.

---

## 7. Commit History

```
dcc4ab54 fix(rust-io): preserve files facade compatibility
c8bcb8f1 refactor(src): import from rust_io facade
06170c5f chore(backend): switch dependency from files-io to rust-io
23491257 fix(rust-io): register facade submodules for Python imports
a44b33cb feat(rust-io): add pyproject.toml for Python package installation
f04b0c52 refactor(rust-io): replace duplicate code with facade delegating to files-io and literature-io
8e996c86 feat(literature-io): add all Rust source files
80d09553 refactor(literature-io): convert to rlib-only, remove pymodule entry point
1e22e101 refactor(files-io): convert to rlib-only, remove pymodule entry point
```

---

## 8. Files Reviewed (Complete List)

### Rust — `rust-io` (facade)
- `backend/libs/rust-io/Cargo.toml`
- `backend/libs/rust-io/pyproject.toml`
- `backend/libs/rust-io/src/lib.rs`

### Rust — `files-io`
- `backend/libs/files-io/Cargo.toml`
- `backend/libs/files-io/src/lib.rs`
- `backend/libs/files-io/src/error.rs`
- `backend/libs/files-io/src/hash.rs`
- `backend/libs/files-io/src/backends/mod.rs`
- `backend/libs/files-io/src/backends/local.rs`
- `backend/libs/files-io/src/backends/s3.rs`
- `backend/libs/files-io/src/archive/mod.rs`
- `backend/libs/files-io/src/archive/zip.rs`
- `backend/libs/files-io/src/archive/tar_gz.rs`
- `backend/libs/files-io/src/py/mod.rs`
- `backend/libs/files-io/src/py/utils.rs`
- `backend/libs/files-io/src/py/file.rs`
- `backend/libs/files-io/src/py/dedup.rs`
- `backend/libs/files-io/src/py/parallel.rs`

### Rust — `literature-io`
- `backend/libs/literature-io/Cargo.toml`
- `backend/libs/literature-io/src/lib.rs`
- `backend/libs/literature-io/src/error.rs`
- `backend/libs/literature-io/src/types.rs`
- `backend/libs/literature-io/src/client.rs`
- `backend/libs/literature-io/src/scraper.rs`
- `backend/libs/literature-io/src/py.rs`
- `backend/libs/literature-io/src/providers/mod.rs`
- `backend/libs/literature-io/src/providers/crossref.rs`
- `backend/libs/literature-io/src/providers/openalex.rs`
- `backend/libs/literature-io/src/providers/europepmc.rs`
- `backend/libs/literature-io/src/providers/pmc.rs`
- `backend/libs/literature-io/src/providers/doaj.rs`
- `backend/libs/literature-io/src/providers/jstage.rs`
- `backend/libs/literature-io/src/providers/unpaywall.rs`

### Python
- `backend/pyproject.toml`
- `backend/src/core/ingest_and_digitize_data/literature_acquisition/gateway.py`
- `backend/src/core/ingest_and_digitize_data/literature_acquisition/web/base.py`
- `backend/src/core/ingest_and_digitize_data/user_upload/service.py`

### Tests
- `backend/tests/core/ingest_and_digitize_data/test_rust_io_facade.py`
- `backend/libs/files-io/tests/test_files_io.py` (dead — blocking)
- `backend/libs/files-io/tests/py_utils.rs`
