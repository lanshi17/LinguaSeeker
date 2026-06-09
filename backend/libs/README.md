# Native Extensions

> Rust/PyO3 native extensions for ACMG Lingua -- literature acquisition, MinerU document parsing, file I/O (local + S3), archive handling, and SHA-256 deduplication. Three crates, one Python module: `rust_io`.

## Crate Map

```
rust-io  (cdylib + rlib)  <-  the ONLY crate built as a Python extension
 |-- net-io    (rlib)      <-  HTTP/web I/O: 14 literature providers + MinerU API
 |-- files-io  (rlib)      <-  File I/O: local + S3, archives, SHA-256 dedup
```

| Crate | Python module | Built as |
|-------|--------------|----------|
| `rust-io` | `rust_io` | `cdylib` (`.so`/`.pyd`) -- loaded by `import rust_io` |
| `net-io` | `rust_io.net` | `rlib` -- statically linked into `rust-io` |
| `files-io` | `rust_io.files` | `rlib` -- statically linked into `rust-io` |

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

# File I/O -- same API for local and S3 paths
import rust_io.files as files_io
f = files_io.File("/tmp/output/report.txt")
f.write("variant analysis results")
print(f.read(as_text=True))

# S3 with explicit credentials
s3f = files_io.File("s3://bucket/data.csv", access_key="AKIA...", secret_key="...")
```

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

## Environment Variables

| Variable | Used by | Description |
|----------|---------|-------------|
| `UNPAYWALL_EMAIL` | `net-io` (Unpaywall) | Required for Unpaywall API |
| `AWS_ACCESS_KEY_ID` | `files-io` (S3) | AWS credential chain (optional if passed explicitly) |
| `AWS_SECRET_ACCESS_KEY` | `files-io` (S3) | AWS credential chain |
| `AWS_REGION` | `files-io` (S3) | Default `us-east-1` |

S3 credentials resolve via the `aws-sdk-s3` default chain (env vars, `~/.aws/credentials`, IMDS). Explicit kwargs override the chain. MinerU tokens are per-call -- never from the environment.

## Sub-crate Reference

- **[rust-io](./rust-io/README.md)** -- Facade crate: submodule registration, full Python API reference
- **[net-io](./net-io/README.md)** -- HTTP I/O: 14 literature providers, MinerU API v4, scraper
- **[files-io](./files-io/README.md)** -- File I/O: `File` class, `FileOps` trait, backends, archives, dedup
