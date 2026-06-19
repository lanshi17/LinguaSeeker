# rust-io

> PyO3 facade crate for CrossEvidence's Rust native extensions. Registers two Python submodules -- `rust_io.net` and `rust_io.files` -- backed by the `net-io` and `files-io` rlib crates.

## Python Usage

```python
import rust_io.net as net_io
import rust_io.files as files

# Literature acquisition
result = await net_io.fetch_one("crossref", "search", {"query": "CRISPR"})

# Download a file from URL
dl = await net_io.download_file("https://example.com/paper.pdf")

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

Requires Python >= 3.10.

## Architecture

```
rust-io (cdylib + rlib)
 |
 +-- src/lib.rs              # #[pymodule] facade -- registers two submodules
 |
 +-- files-io (rlib dep)     # File I/O, S3, archives, SHA-256 dedup
 |   +-- src/py/file.rs      #   File #[pyclass]
 |   +-- src/py/parallel.rs  #   batch_copy, batch_compress, batch_copy_async
 |   +-- src/py/dedup.rs     #   check_duplicate, batch_hash
 |   +-- src/py/utils.rs     #   compute_sha256, write_file, validate_pdf_magic
 |
 +-- net-io (rlib dep)       # HTTP/web I/O (15 providers, scraper, MinerU API)
     +-- src/py.rs           #   fetch_one, fetch_multi, scrape_web, scrape_html,
                             #   extract_pdf_links, download_file, mineru_* (8 functions)
```

This crate contains no business logic. `src/lib.rs` only:
1. Creates a `PyModule` for each submodule (`"net"`, `"files"`)
2. Adds `#[pyfunction]`s and `#[pyclass]`es from sub-crates via `wrap_pyfunction!` / `add_class`
3. Registers each submodule in `sys.modules` via `register_submodule()` so `import rust_io.net` and `import rust_io.files` work as top-level imports

## Sub-crate Docs

- [net-io](../net-io/) -- HTTP/web I/O providers + MinerU document parsing
- [files-io](../files-io/) -- File I/O, S3, archives, SHA-256 dedup

## Dependencies

| Crate | Version | Purpose |
|-------|---------|---------|
| pyo3 | 0.28.2 | Rust-to-Python bindings |
| pyo3-async-runtimes | 0.28 | async fn -> Python coroutine (tokio) |
| files-io | path | Sub-crate providing `rust_io.files` functions |
| net-io | path | Sub-crate providing `rust_io.net` functions |

All business-logic dependencies are in the sub-crates. The facade only depends on `pyo3`, `pyo3-async-runtimes`, and the two sub-crates.
