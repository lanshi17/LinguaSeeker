# Native Extensions

> Rust/PyO3 native extensions for ACMG Lingua — literature acquisition, MinerU document parsing, file I/O (local + S3), archive handling, and SHA-256 deduplication. Three crates, one Python module: `rust_io`.

## Crate Map

```
rust-io  (cdylib + rlib)  ←  the ONLY crate built as a Python extension
 ├── net-io    (rlib)      ←  HTTP/web I/O: 7 literature providers + MinerU API
 └── files-io  (rlib)      ←  File I/O: local + S3, archives, SHA-256 dedup
```

| Crate | Python module | Built as |
|-------|--------------|----------|
| `rust-io` | `rust_io` | `cdylib` (`.so`/`.pyd`) — loaded by `import rust_io` |
| `net-io` | `rust_io.net` | `rlib` — statically linked into `rust-io` |
| `files-io` | `rust_io.files` | `rlib` — statically linked into `rust-io` |

`net-io` and `files-io` are **not** standalone Python modules. They expose `#[pyfunction]`s and `#[pyclass]`es that the `rust-io` facade registers as two submodules (`rust_io.net`, `rust_io.files`) via `register_submodule()`.

## Quick Start

```python
# Literature search (single provider)
import rust_io.net as net_io
result = await net_io.fetch_one("crossref", "search", {"query": "CRISPR"})

# Parallel multi-provider search
results = await net_io.fetch_multi(
    ["crossref", "openalex", "europepmc"],
    "search",
    {"query": "BRCA1 variant", "limit": 5},
)

# File I/O — same API for local and S3 paths
import rust_io.files as files_io
f = files_io.File("/tmp/output/report.txt")
f.write("variant analysis results")
print(f.read(as_text=True))

# S3 with explicit credentials
s3f = files_io.File("s3://bucket/data.csv", access_key="AKIA...", secret_key="...")
```

## Architecture

### Data flow

```
Python caller
  │ import rust_io.net / import rust_io.files
  ▼
rust_io (facade)          src/lib.rs: #[pymodule] registers two submodules
  ├── rust_io.net   ──►  net_io::py::*        param parsing → provider dispatch → HttpClient → external APIs
  └── rust_io.files ──►  files_io::py::*      path inspection → Backend enum → FileOps trait → local/S3
```

**`rust_io` facade** (`src/lib.rs`) contains zero business logic. It:
1. Creates `PyModule` instances for `"net"` and `"files"`
2. Registers `#[pyfunction]`s / `#[pyclass]`es from sub-crates via `wrap_pyfunction!` / `add_class`
3. Calls `register_submodule()` which does `parent.add_submodule()` + `sys.modules["rust_io.<name>"] = submodule` — needed because PyO3 nests submodules by default

**`net-io`** — `src/py.rs` parses Python `dict` params into typed Rust structs, dispatches to provider implementations in `src/providers/`, and serializes results back via `pythonize`. MinerU functions follow the same pattern through `src/mineru.rs`.

**`files-io`** — `src/py/file.rs` inspects the path prefix: `s3://` constructs `S3Backend`; everything else uses `LocalBackend`. Both implement the `FileOps` trait, so callers never branch on backend.

### Concurrency model

All async Python functions use `pyo3-async-runtimes` to bridge Rust `async fn` → Python coroutine. The underlying tokio runtime is shared automatically:

- **Provider I/O** (`net-io`): `HttpClient` is created per-call with configurable timeout + retry. `fetch_multi` launches all providers concurrently via `futures::join_all` — failures are captured per-provider, not propagated.
- **File I/O** (`files-io`): Synchronous methods run directly. Async variants (`*_async`) wrap `tokio::task::spawn_blocking` so blocking I/O doesn't stall the Python event loop. The S3 backend uses a shared `OnceLock<Runtime>` singleton for sync→async bridging.
- **GIL**: held during argument parsing, released during async I/O, re-acquired only for return value construction via `pythonize`.

## Build & Install

```bash
# Build the Python extension (from backend/)
cd backend
uv run maturin develop --release -m libs/rust-io/Cargo.toml

# Run Rust unit tests per sub-crate
cargo test -p net-io
cargo test -p files-io

# Run Python integration tests
uv run pytest backend/tests/ -v

# Lint Rust
cargo clippy --all-targets -- -D warnings

# Lint Python
uv run ruff check
```

Each crate has its own `Cargo.lock` (not a workspace). After adding/updating dependencies, run `cargo check` from the crate directory.

## Error Handling

Both sub-crates map Rust error types to Python exceptions automatically via `From<Error> for PyErr`:

### rust_io.net (`GatewayError`)

| Rust variant | Python exception | Typical cause |
|-------------|-----------------|---------------|
| `Http(reqwest::Error)` | `ConnectionError` | Timeout, DNS failure, non-2xx |
| `Json(serde_json::Error)` | `ValueError` | Malformed provider response |
| `Io(std::io::Error)` | `OSError` | File read failure (MinerU upload) |
| `Url(url::ParseError)` | `ValueError` | Malformed URL |
| `Provider { provider, message }` | `RuntimeError` | Unknown provider or unsupported action |
| `Other(String)` | `RuntimeError` | Catch-all |

### rust_io.files (`FileError`)

| Rust variant | Python exception | Typical cause |
|-------------|-----------------|---------------|
| `Io(std::io::Error)` | `IOError` | Permission denied, file not found |
| `S3(String)` | `ConnectionError` | S3 unavailable, auth failure |
| `Path(String)` | `ValueError` | Path traversal attempt |
| `Archive(String)` | `ValueError` | Malformed archive |
| `Zip(ZipError)` | `ValueError` | Corrupt ZIP |
| `Hash(String)` | `RuntimeError` | SHA-256 computation failure |
| `TaskJoin(JoinError)` | `RuntimeError` | spawn_blocking panic |
| `Other(String)` | `RuntimeError` | Catch-all |

## rust_io.net — API at a Glance

### Literature Providers

| Function | Description |
|----------|-------------|
| `fetch_one(provider, action, params, ...)` | Single provider search/download |
| `fetch_multi(providers, action, params, ...)` | Parallel multi-provider via `join_all` |
| `scrape_web(provider, action, params, ...)` | Generic web scraping with CSS selectors |
| `scrape_html(html, css_selector)` | Extract elements by CSS selector from HTML string |
| `extract_pdf_links(html, base_url)` | Find PDF URLs in `<a href>` and `<meta citation_pdf_url>` |

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

## rust_io.files — API at a Glance

### File class

Constructor: `File(path, access_key=None, secret_key=None, endpoint=None, region=None)`

| Method | Description |
|--------|-------------|
| `read(as_text=False) → bytes | str` | Read entire file |
| `read_chunk(offset, size) → bytes` | Read byte range |
| `write(data) → None` | Write bytes or str, creates parent dirs |
| `exists() → bool` | Check existence |
| `metadata() → dict` | Size, mtime, permissions, backend extras |
| `rename(dst) → None` | Move/rename |
| `copy(dst) → None` | Copy (cross-backend if dst is S3) |
| `remove() → None` | Delete |
| `remove_dir_all() → None` | Recursive delete |
| `list_dir() → list[str]` | List directory entries |
| `content_hash() → str` | SHA-256 hex digest |
| `compress(output_path, format) → int` | Archive directory (zip/tar/tar.gz) |
| `extract(output_dir) → int` | Extract archive (auto-detect format) |
| `copy_async(dst) → Awaitable[None]` | Async copy |
| `compress_async(output_path, format) → Awaitable[int]` | Async compress |
| `extract_async(output_dir) → Awaitable[int]` | Async extract |

### Module-level functions

| Function | Description |
|----------|-------------|
| `batch_copy(sources, destinations, ...)` | Sequential multi-file copy (mixed local/S3) |
| `batch_compress(dir_paths, output_paths, format="zip")` | Sequential multi-directory compression |
| `batch_copy_async(sources, destinations, ...)` | Async batch copy |
| `check_duplicate(file_path, known_hashes) → dict` | Hash + dedup check |
| `batch_hash(file_paths) → dict` | Hash multiple files |
| `compute_sha256(file_path) → str` | Legacy: SHA-256 of a single file |
| `write_file(file_path, data) → None` | Legacy: write bytes to file |
| `validate_pdf_magic(data) → bool` | Check `%PDF` header |

## Environment Variables

| Variable | Used by | Description |
|----------|---------|-------------|
| `UNPAYWALL_EMAIL` | `net-io` (Unpaywall) | Required for Unpaywall API |
| `AWS_ACCESS_KEY_ID` | `files-io` (S3) | AWS credential chain (optional if passed explicitly) |
| `AWS_SECRET_ACCESS_KEY` | `files-io` (S3) | AWS credential chain |
| `AWS_REGION` | `files-io` (S3) | Default `us-east-1` |

S3 credentials resolve via the `aws-sdk-s3` default chain (env vars, `~/.aws/credentials`, IMDS). Explicit kwargs override the chain. MinerU tokens are per-call — never from the environment.

## Sub-crate Reference

- **[rust-io](./rust-io/README.md)** — Facade crate: submodule registration, full Python API reference, extension guide
- **[net-io](./net-io/README.md)** — HTTP I/O: providers, HttpClient, MinerU API v4, scraper, error reference
- **[files-io](./files-io/README.md)** — File I/O: `File` class, `FileOps` trait, backends, archives, dedup, tests

## Extension Guide

### Adding a new literature provider

1. Implement the provider in `net-io/src/providers/<name>.rs` (follow `CrossrefProvider` pattern)
2. Register it in `net-io/src/providers/mod.rs`
3. Add the match arm in `net-io/src/py.rs` → `execute_provider()`
4. Rebuild: `uv run maturin develop --release -m libs/rust-io/Cargo.toml`

### Adding a new Python function to `rust_io.net`

1. Implement the Rust logic in `net-io/src/`
2. Expose as `#[pyfunction]` in `net-io/src/py.rs`
3. Register in `rust-io/src/lib.rs`: `net.add_function(wrap_pyfunction!(net_io::py::new_fn, &net)?)?;`
4. Rebuild

### Adding a new Python function to `rust_io.files`

Same pattern — implement in `files-io/src/py/`, register in `rust-io/src/lib.rs` under the `files` module.

### Submodule registration internals

```rust
fn register_submodule(
    parent: &Bound<'_, PyModule>,
    full_name: &str,         // e.g. "rust_io.net"
    submodule: &Bound<'_, PyModule>,
) -> PyResult<()> {
    parent.add_submodule(submodule)?;
    parent.py().import("sys")?
        .getattr("modules")?
        .cast::<PyDict>()?
        .set_item(full_name, submodule)?;
    Ok(())
}
```

Without the `sys.modules` registration, `import rust_io.net` would fail because PyO3 only nests modules by default — it doesn't make them importable as top-level names.

## Dependencies

### rust-io (facade)

| Crate | Version | Purpose |
|-------|---------|---------|
| pyo3 | 0.28.2 | Rust↔Python bindings |
| pyo3-async-runtimes | 0.28 | async fn → Python coroutine |
| files-io | path | Sub-crate: file I/O |
| net-io | path | Sub-crate: HTTP I/O |

### net-io

| Crate | Purpose |
|-------|---------|
| reqwest | HTTP client (rustls, gzip, socks proxy) |
| scraper | HTML parsing + CSS selectors |
| tokio | Async runtime |
| serde / serde_json | Serialization |
| url / urlencoding | URL handling |
| pythonize | Rust struct → Python dict |

### files-io

| Crate | Purpose |
|-------|---------|
| aws-sdk-s3 / aws-config / aws-credential-types | S3 backend |
| tokio | Async runtime + blocking thread pool |
| sha2 / hex | SHA-256 hashing |
| zip / tar / flate2 | Archive handling |
| serde / serde_json | Serialization |
| pythonize | Rust struct → Python dict |
