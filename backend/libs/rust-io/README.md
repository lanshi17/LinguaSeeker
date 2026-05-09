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
                             #   extract_pdf_links, mineru_* (4 functions)
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

## Dependencies

| Crate | Version | Purpose |
|-------|---------|---------|
| pyo3 | 0.28.2 | Rust-to-Python bindings (`extension-module` feature) |
| pyo3-async-runtimes | 0.28 | async fn → Python coroutine (tokio) |
| files-io | path = "../files-io" | Sub-crate providing `rust_io.files` functions |
| net-io | path = "../net-io" | Sub-crate providing `rust_io.net` functions |

All business-logic dependencies are in the sub-crates. The facade only depends on `pyo3`, `pyo3-async-runtimes`, and the two sub-crates.
