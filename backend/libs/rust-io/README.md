# rust-io

Thin PyO3 facade for ACMG Lingua's Rust native extensions. Registers `rust_io.files` and `rust_io.http` submodules backed by `files-io` and `http-io` crates.

## Python Usage

```python
import rust_io.files as files
import rust_io.http as http_io

# Literature acquisition
result = await http_io.fetch_one("crossref", "search", {"query": "CRISPR"})

# MinerU document parsing
task = await http_io.mineru_create_task("https://example.com/paper.pdf", token="...")

# File I/O
files.write_file("/tmp/test.bin", b"hello")
sha = files.compute_sha256("/tmp/test.bin")
```

## Build & Install

```bash
cd backend
uv run maturin develop --release -m libs/rust-io/Cargo.toml
```

## Architecture

```
rust-io (cdylib + rlib)
├── src/lib.rs              # Facade: registers submodules
├── files-io (rlib)         # File I/O, S3, archives, dedup
│   └── src/py/             # #[pyfunction]s re-exported by facade
└── http-io (rlib)          # HTTP/web I/O (7 providers, scraper, MinerU API)
    └── src/py/             # #[pyfunction]s re-exported by facade
```

The facade delegates all functionality to sub-crates. `src/lib.rs` only:
1. Creates `PyModule` for each submodule (`"files"`, `"http"`)
2. Adds `#[pyfunction]` / `#[pyclass]` from sub-crates via `wrap_pyfunction!` / `add_class`
3. Registers each submodule in `sys.modules` so `import rust_io.files` works

## Exports

### `rust_io.http`

#### Literature Providers

| Function | Description |
|----------|-------------|
| `fetch_one(provider, action, params, ...)` | Single-provider search/download |
| `fetch_multi(providers, action, params, ...)` | Multi-provider parallel search |
| `scrape_web(provider, action, params, ...)` | Generic web scraping |
| `scrape_html(html, css_selector)` | CSS selector extraction |
| `extract_pdf_links(html, base_url)` | PDF link extraction |

#### MinerU Document Parsing

| Function | Description |
|----------|-------------|
| `mineru_create_task(url, token, ...)` | Create a single document parsing task |
| `mineru_get_result(task_id, token, ...)` | Get single task result |
| `mineru_batch_submit(files, token, ...)` | Submit batch parsing tasks |
| `mineru_batch_result(batch_id, token, ...)` | Get batch results |

### `rust_io.files`

| Item | Description |
|------|-------------|
| `File` | File read/write class |
| `batch_copy(sources, destinations, ...)` | Sequential file copy |
| `batch_compress(dir_paths, output_paths, format)` | Archive compression |
| `batch_copy_async(sources, destinations, ...)` | Non-blocking sequential batch copy |
| `check_duplicate(path)` | SHA256 dedup check |
| `batch_hash(paths)` | Batch SHA256 hashing |
| `compute_sha256(path)` | Legacy helper |
| `write_file(path, data)` | Legacy helper |
| `validate_pdf_magic(data)` | Legacy helper |

## Sub-crate Docs

- [files-io](../files-io/) — File I/O, S3, archives
- [http-io](../http-io/) — HTTP/web I/O providers + MinerU document parsing
