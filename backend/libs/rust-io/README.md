# rust-io

> PyO3 facade crate for ACMG Lingua's Rust native extensions. Registers two Python submodules — `rust_io.net` and `rust_io.files` — backed by the `net-io` and `files-io` rlib crates.

## Python Usage

```python
import rust_io.net as net_io
import rust_io.files as files

# Literature acquisition
result = await net_io.fetch_one("crossref", "search", {"query": "CRISPR"})

# MinerU document parsing
task = await net_io.mineru_create_task("https://example.com/paper.pdf", token="...")

# File I/O
f = files.File("/tmp/data/report.txt")
f.write("patient variant report")
content = f.read(as_text=True)

# SHA-256 hashing and dedup
sha = files.compute_sha256("/tmp/data/report.txt")
dup_result = files.check_duplicate("/tmp/data/report.txt", [sha])
```

## Build & Install

```bash
cd backend
uv run maturin develop --release -m libs/rust-io/Cargo.toml
```

Requires Python >= 3.8.

## Architecture

```
rust-io (cdylib + rlib)
 │
 ├── src/lib.rs              # #[pymodule] facade — registers two submodules
 │
 ├── files-io (rlib dep)     # File I/O, S3, archives, SHA-256 dedup
 │   ├── src/py/file.rs      #   File #[pyclass]
 │   ├── src/py/parallel.rs  #   batch_copy, batch_compress, batch_copy_async
 │   ├── src/py/dedup.rs     #   check_duplicate, batch_hash
 │   └── src/py/utils.rs     #   compute_sha256, write_file, validate_pdf_magic
 │
 └── net-io (rlib dep)       # HTTP/web I/O (7 providers, scraper, MinerU API)
     └── src/py.rs           #   fetch_one, fetch_multi, scrape_web, scrape_html,
                             #   extract_pdf_links, mineru_* (8 functions)
```

This crate contains no business logic. `src/lib.rs` only:
1. Creates a `PyModule` for each submodule (`"net"`, `"files"`)
2. Adds `#[pyfunction]`s and `#[pyclass]`es from sub-crates via `wrap_pyfunction!` / `add_class`
3. Registers each submodule in `sys.modules` via `register_submodule()` so `import rust_io.net` and `import rust_io.files` work as top-level imports

The `register_submodule` helper calls `parent.add_submodule(submodule)` and then sets `sys.modules["rust_io.<name>"]` to the submodule. This is necessary because PyO3 modules are nested by default; without sys.modules registration, `import rust_io.net` would fail.

## Exports

### `rust_io.net`

#### Literature Providers

| Function | Signature | Description |
|----------|-----------|-------------|
| `fetch_one` | `(provider, action, params, timeout_ms=None, max_retries=None, proxy=None) -> dict` | Single-provider search/download. Action must be `"search"` or `"download"`. |
| `fetch_multi` | `(providers, action, params, timeout_ms=None, max_retries=None, proxy=None) -> list[dict]` | Multi-provider parallel search via `join_all`. Failures captured per-provider, not propagated. |
| `scrape_web` | `(provider, action, params, timeout_ms=None, max_retries=None, proxy=None) -> dict` | Generic web scraping. Fetches HTML, extracts elements by CSS selector. Derives URL from `params.detail_link` or `params.query`. |
| `scrape_html` | `(html, css_selector) -> list[dict]` | CSS selector extraction from HTML. Returns `[{text, html, tag_name, attrs}, ...]`. |
| `extract_pdf_links` | `(html, base_url) -> list[str]` | Extract PDF URLs from `<a href>` and `<meta citation_pdf_url>`. Resolves relative URLs against `base_url`. |

#### MinerU Document Parsing

| Function | Signature | Description |
|----------|-----------|-------------|
| `mineru_create_task` | `(url, token, model_version=None, is_ocr=None, enable_formula=None, enable_table=None, language=None, data_id=None, page_ranges=None, no_cache=None, cache_tolerance=None, timeout_ms=None, proxy=None) -> dict` | Create a single document parsing task. POST to MinerU API v4. |
| `mineru_get_result` | `(task_id, token, timeout_ms=None, proxy=None) -> dict` | Get single task result by ID. |
| `mineru_batch_submit` | `(files, token, model_version=None, enable_formula=None, enable_table=None, language=None, no_cache=None, cache_tolerance=None, timeout_ms=None, proxy=None) -> dict` | Submit batch parsing tasks. `files` is `list[dict]` with `url`, optional `data_id`, `is_ocr`, `page_ranges`. |
| `mineru_batch_result` | `(batch_id, token, timeout_ms=None, proxy=None) -> dict` | Get batch results by batch ID. |
| `mineru_create_upload_url` | `(filename, token, content_type=None, model_version=None, is_ocr=None, enable_formula=None, enable_table=None, language=None, data_id=None, page_ranges=None, no_cache=None, cache_tolerance=None, timeout_ms=None, proxy=None) -> dict` | Get a pre-signed upload URL for a local file (single). POST to MinerU API v4 `/file-urls/batch`. |
| `mineru_create_batch_upload_urls` | `(files, token, model_version=None, enable_formula=None, enable_table=None, language=None, callback=None, seed=None, extra_formats=None, timeout_ms=None, proxy=None) -> dict` | Get pre-signed upload URLs for multiple local files. Uploaded files are auto-submitted by MinerU. |
| `mineru_upload_local_files` | `(file_paths, token, model_version=None, enable_formula=None, enable_table=None, language=None, data_ids=None, is_ocr=None, page_ranges=None, callback=None, seed=None, extra_formats=None, timeout_ms=None, proxy=None) -> dict` | Create upload URLs and upload local files. MinerU auto-submits after upload. |
| `mineru_upload_local_file` | `(upload_url, file_path, content_type=None, timeout_ms=None, proxy=None) -> dict` | Upload a single local file to a pre-signed URL. |
### `rust_io.files`

| Item | Type | Description |
|------|------|-------------|
| `File` | class | Primary file I/O class. Path prefix (`s3://` vs local) auto-selects backend. Supports read, write, metadata, copy, rename, remove, list_dir, compress, extract, content_hash, and async variants. |
| `batch_copy` | function | `(sources: list[str], destinations: list[str], access_key=None, secret_key=None, endpoint=None, region=None) -> dict` — sequential copy with mixed local/S3 support. |
| `batch_compress` | function | `(dir_paths: list[str], output_paths: list[str], format="zip") -> dict` — sequential directory compression. |
| `batch_copy_async` | function | `(sources, destinations, access_key=None, secret_key=None, endpoint=None, region=None) -> dict` — non-blocking variant of `batch_copy`. |
| `check_duplicate` | function | `(file_path: str, known_hashes: list[str]) -> dict` — SHA-256 hash a file and check against known hashes. Returns `{"hash": str, "is_duplicate": bool}`. |
| `batch_hash` | function | `(file_paths: list[str]) -> dict` — SHA-256 hash multiple files. Returns `{"hashes": {path: hash}, "errors": {path: message}}`. |
| `compute_sha256` | function | `(file_path: str) -> str` — legacy helper; thin wrapper over `hash::hash_file`. Raises `IOError`. |
| `write_file` | function | `(file_path: str, data: bytes) -> None` — legacy helper; thin wrapper over `std::fs::write`. Raises `IOError`. |
| `validate_pdf_magic` | function | `(data: bytes) -> bool` — returns `True` if data starts with `%PDF`. |

## Sub-crate Docs

- [net-io](../net-io/) — HTTP/web I/O providers + MinerU document parsing
- [files-io](../files-io/) — File I/O, S3, archives, SHA-256 dedup


## Concurrency Model

All async Python functions (`fetch_one`, `fetch_multi`, `scrape_web`, `mineru_*`, `batch_copy_async`, etc.) use `pyo3-async-runtimes` to bridge Rust `async fn` → Python coroutine. The underlying tokio runtime is managed automatically:

- **Provider I/O** (`net-io`): Each `HttpClient` is created per-call. `fetch_multi` launches all provider requests concurrently via `futures::join_all` — all providers execute in parallel on the same tokio runtime.
- **File I/O** (`files-io`): Synchronous `File` methods execute directly. Async variants (`*_async`) use `tokio::task::spawn_blocking` to offload blocking I/O without stalling the Python event loop. The S3 backend uses a shared `OnceLock<Runtime>` singleton for sync→async bridging.
- **GIL behavior**: Rust code inside `#[pyfunction]` runs with the GIL held during argument parsing, then releases it during async I/O. The GIL is re-acquired only to construct the return value via `pythonize`.

## Environment Variables

| Variable | Used by | Description |
|----------|---------|-------------|
| `UNPAYWALL_EMAIL` | `net-io` (Unpaywall provider) | Required for Unpaywall API authentication |
| `AWS_ACCESS_KEY_ID` | `files-io` (S3 backend) | AWS credential chain (optional if passed explicitly) |
| `AWS_SECRET_ACCESS_KEY` | `files-io` (S3 backend) | AWS credential chain (optional if passed explicitly) |
| `AWS_REGION` | `files-io` (S3 backend) | AWS region, default `us-east-1` |

S3 credential resolution uses the `aws-sdk-s3` default credential chain (env vars, `~/.aws/credentials`, IMDS). Explicit `access_key`/`secret_key`/`region` kwargs override the chain. MinerU tokens are passed per-call — they are never read from the environment.

## Error Reference

Both sub-crates map Rust error types to Python exceptions automatically via `From<Error> for PyErr`:

### `rust_io.net` (GatewayError)

| Rust variant | Python exception | Typical cause |
|-------------|-----------------|---------------|
| `Http(reqwest::Error)` | `ConnectionError` | Timeout, DNS failure, non-2xx response |
| `Json(serde_json::Error)` | `ValueError` | Malformed provider response |
| `Io(std::io::Error)` | `OSError` | File read failure (MinerU upload) |
| `Url(url::ParseError)` | `ValueError` | Malformed provider URL |
| `Provider { provider, message }` | `RuntimeError` | Unknown provider or unsupported action |
| `Other(String)` | `RuntimeError` | Catch-all for business logic errors |

### `rust_io.files` (FileError)

| Rust variant | Python exception | Typical cause |
|-------------|-----------------|---------------|
| `Io(std::io::Error)` | `IOError` | Permission denied, file not found |
| `S3(String)` | `ConnectionError` | S3 service unavailable, auth failure |
| `Path(String)` | `ValueError` | Path traversal attempt, invalid path |
| `Archive(String)` | `ValueError` | Malformed archive, extraction path error |
| `Zip(ZipError)` | `ValueError` | Corrupt ZIP file |
| `Hash(String)` | `RuntimeError` | SHA-256 computation failure |
| `TaskJoin(JoinError)` | `RuntimeError` | spawn_blocking task panic or cancel |
| `Other(String)` | `RuntimeError` | Catch-all for business logic errors |

## Development Workflow

```bash
# Build the Python extension (from backend/)
cd backend
uv run maturin develop --release -m libs/rust-io/Cargo.toml

# Run Rust unit tests per sub-crate
cargo test -p net-io
cargo test -p files-io

# Run Python integration tests
uv run pytest backend/tests/ -v

# Lint Rust code
cargo clippy --all-targets -- -D warnings

# Type-check Python
uv run ruff check
```

The `Cargo.lock` files are committed for reproducibility. After adding or updating dependencies, run `cargo check` from the crate directory (not a workspace root) to update individual lock files.

## Extension Guide

### Adding a new `rust_io.net` pyfunction

1. Implement the Rust function in `net-io/src/` (e.g. a new provider, new scraper utility)
2. Expose it as a `#[pyfunction]` in `net-io/src/py.rs`
3. Register it in `rust-io/src/lib.rs`:
   ```rust
   net.add_function(wrap_pyfunction!(net_io::py::your_new_function, &net)?)?;
   ```
4. Rebuild and test

### Adding a new `rust_io.files` pyfunction

Same pattern — implement in `files-io/src/py/`, then register in `rust-io/src/lib.rs`:
```rust
files.add_function(wrap_pyfunction!(files_io::py::new_module::your_function, &files)?)?;
```

### Submodule registration internals

The `register_submodule` helper is required because PyO3 nests submodules by default. Without explicitly setting `sys.modules["rust_io.net"]`, Python's `import rust_io.net` would fail even though the module is attached to the parent. The helper calls both `parent.add_submodule()` and `sys.modules[full_name] = submodule`.
## Dependencies

| Crate | Version | Purpose |
|-------|---------|---------|
| pyo3 | 0.28.2 | Rust-to-Python bindings (`extension-module` feature) |
| pyo3-async-runtimes | 0.28 | async fn → Python coroutine (tokio) |
| files-io | path = "../files-io" | Sub-crate providing `rust_io.files` functions |
| net-io | path = "../net-io" | Sub-crate providing `rust_io.net` functions |

All business-logic dependencies are in the sub-crates. The facade only depends on `pyo3`, `pyo3-async-runtimes`, and the two sub-crates.
