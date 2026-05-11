# files-io

> Unified local + S3 file I/O for ACMG Lingua, implemented as a Rust/PyO3 native extension. Provides a single `File` class that transparently dispatches to local filesystem or Amazon S3, plus batch operations, archive handling, and SHA-256 deduplication.

## Quick Start

```python
import rust_io.files as files_io

# Local file — write and read
f = files_io.File("/tmp/data/report.txt")
f.write("patient variant report")
print(f.read(as_text=True))  # "patient variant report"

# S3 file — same API, pass credentials
s3f = files_io.File(
    "s3://my-bucket/reports/report.txt",
    access_key="AKIA...",
    secret_key="secret...",
    endpoint="http://localhost:9000",  # optional, for MinIO etc.
)
s3f.write(b"binary data")

# Hash for deduplication
result = files_io.check_duplicate("/tmp/data/report.txt", [f.content_hash()])
print(result["is_duplicate"])  # True
```

## Architecture

```
Python caller
     |
     v
+---------------------+
|   files_io (PyO3)   |   <-- lib.rs: #[pymodule]
|                     |
|  File (pyclass)     |   <-- py/file.rs
|  batch_copy()       |   <-- py/parallel.rs
|  batch_compress()   |
|  batch_copy_async() |
|  check_duplicate()  |   <-- py/dedup.rs
|  batch_hash()       |
+----------+----------+
           |
           v
+----------+----------+
|   FileOps trait     |   <-- backends/mod.rs
|   + FileMetadata    |
+-----+---------+-----+
      |         |
      v         v
+-----+--+  +--+-----+
| Local   |  |  S3    |   <-- backends/local.rs, backends/s3.rs
| Backend |  | Backend|
+---------+  +--------+

     Archive subsystem         Hash subsystem
     (archive/zip.rs,          (hash.rs)
      archive/tar_gz.rs)

All Rust errors (FileError) convert to PyErr automatically.
```

Data flow: Python calls `File(path)` which inspects the path prefix. If it starts with `s3://`, the S3 backend is constructed with the provided credentials; otherwise the local backend is used. All subsequent operations dispatch through the `FileOps` trait, so the caller never needs to know which backend is active.

## Public API

### `File`

The primary Python class. Constructed with a path (local or `s3://`), it provides read/write/metadata/archive operations. Works as a context manager.

**Constructor:**

```python
File(
    path: str,
    access_key: str | None = None,   # required for s3:// paths
    secret_key: str | None = None,   # required for s3:// paths
    endpoint: str | None = None,     # custom S3 endpoint (e.g. MinIO)
    region: str | None = None,       # AWS region, defaults to "us-east-1"
)
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `read` | `(as_text: bool = False) -> bytes \| str` | Read entire file. Returns `bytes` by default, `str` if `as_text=True`. |
| `read_chunk` | `(offset: int, size: int) -> bytes` | Read `size` bytes starting at `offset`. Uses `seek` for local, HTTP Range for S3. |
| `write` | `(data: bytes \| str) -> None` | Write data to file. Accepts `bytes` or `str`. Creates parent directories automatically. |
| `exists` | `() -> bool` | Check if the file exists. |
| `metadata` | `() -> dict` | Returns dict with `size`, `mtime`, `is_file`, `is_dir`, `is_symlink`, `permissions`, and backend-specific extras (e.g. `etag`, `inode`). |
| `rename` | `(dst: str) -> None` | Move/rename the file. For S3, this is copy + delete. |
| `copy` | `(dst: str) -> None` | Copy the file to a new location. Supports cross-backend if destination is S3. |
| `remove` | `() -> None` | Delete the file. |
| `remove_dir_all` | `() -> None` | Recursively delete a directory (local) or all objects under a prefix (S3). |
| `list_dir` | `() -> list[str]` | List entries in a directory or S3 prefix. |
| `content_hash` | `() -> str` | SHA-256 hex digest. Local: reads file in 1MB chunks. S3: downloads then hashes. |
| `compress` | `(output_path: str, format: str) -> int` | Compress directory to `"zip"`, `"tar"`, or `"tar.gz"`. Returns number of files compressed. |
| `extract` | `(output_dir: str) -> int` | Extract archive (auto-detects format from extension). Returns number of files extracted. |
| `copy_async` | `(dst: str) -> Awaitable[None]` | Async version of `copy`. Uses `tokio::task::spawn_blocking`. |
| `compress_async` | `(output_path: str, format: str) -> Awaitable[int]` | Async version of `compress`. |
| `extract_async` | `(output_dir: str) -> Awaitable[int]` | Async version of `extract`. |

### Module-level functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `batch_copy` | `(sources: list[str], destinations: list[str], access_key=None, secret_key=None, endpoint=None, region=None) -> dict` | Copy multiple files sequentially. Auto-selects local or S3 backend per path. Returns `{"success": [...], "failed": [{"path", "error"}]}`. |
| `batch_compress` | `(dir_paths: list[str], output_paths: list[str], format: str = "zip") -> dict` | Compress multiple directories. Returns same result structure as `batch_copy`. |
| `batch_copy_async` | `(sources, destinations, access_key=None, secret_key=None, endpoint=None, region=None) -> Awaitable[dict]` | Async version of `batch_copy`. |
| `check_duplicate` | `(file_path: str, known_hashes: list[str]) -> dict` | Hash a file and check against known hashes. Returns `{"hash": str, "is_duplicate": bool}`. |
| `batch_hash` | `(file_paths: list[str]) -> dict` | Hash multiple files. Returns `{"hashes": {path: hash}, "errors": {path: message}}`. |

### `FileOps` trait (Rust)

The internal abstraction that both backends implement. Not exposed to Python directly, but relevant if extending the module.

```rust
pub trait FileOps: Send + Sync {
    fn read_all(&self, path: &str) -> Result<Vec<u8>, FileError>;
    fn read_chunk(&self, path: &str, offset: u64, size: u64) -> Result<Vec<u8>, FileError>;
    fn write(&self, path: &str, data: &[u8], create_parents: bool) -> Result<(), FileError>;
    fn write_stream(&self, path: &str, reader: &mut dyn Read, create_parents: bool) -> Result<(), FileError>;
    fn exists(&self, path: &str) -> Result<bool, FileError>;
    fn metadata(&self, path: &str) -> Result<FileMetadata, FileError>;
    fn rename(&self, src: &str, dst: &str) -> Result<(), FileError>;
    fn copy(&self, src: &str, dst: &str) -> Result<(), FileError>;
    fn remove(&self, path: &str) -> Result<(), FileError>;
    fn remove_dir_all(&self, path: &str) -> Result<(), FileError>;
    fn list_dir(&self, path: &str) -> Result<Vec<String>, FileError>;
    fn ensure_dir(&self, path: &str) -> Result<(), FileError>;
}
```

### `FileMetadata` (Rust)

```rust
pub struct FileMetadata {
    pub size: u64,
    pub mtime: f64,         // seconds since UNIX epoch
    pub is_file: bool,
    pub is_dir: bool,
    pub is_symlink: bool,
    pub permissions: String, // octal string on Unix, empty on other platforms
    pub extra: HashMap<String, String>,
}
```

The `extra` field carries backend-specific data:
- **Local (Unix):** `mode`, `inode`, `nlink`, `uid`, `gid`
- **S3:** `etag`, `content_type`, `storage_class`

### `FileError` (Rust)

```rust
pub enum FileError {
    Io(std::io::Error),
    S3(String),
    Path(String),
    Archive(String),
    Zip(zip::result::ZipError),
    Hash(String),
    TaskJoin(tokio::task::JoinError),
    Other(String),
}
```

All variants convert to Python exceptions automatically via the `From<FileError> for PyErr` impl:

| Rust variant | Python exception |
|-------------|-----------------|
| `Io(std::io::Error)` | `IOError` |
| `S3(String)` | `ConnectionError` |
| `Path(String)` | `ValueError` |
| `Archive(String)` | `ValueError` |
| `Zip(zip::result::ZipError)` | `ValueError` |
| `Hash(String)` | `RuntimeError` |
| `TaskJoin(tokio::task::JoinError)` | `RuntimeError` |
| `Other(String)` | `RuntimeError` |

## Internal Design

### Backend selection

`File::new()` inspects the path prefix. `s3://` triggers S3 backend construction (credentials required); everything else uses `LocalBackend`. The `batch_copy` function selects the backend per-file, so a single batch can mix local and S3 paths.

### S3 async model

S3 operations are synchronous from Python's perspective but use `tokio::runtime::Runtime::block_on()` internally. A single shared `Runtime` (via `OnceLock<Runtime>`) is reused across all `S3Backend` instances to avoid creating redundant thread pools.

The async variants (`copy_async`, `compress_async`, `extract_async`, `batch_copy_async`) use `pyo3_async_runtimes::tokio::future_into_py` to wrap `tokio::task::spawn_blocking` calls, so the actual I/O runs on the tokio blocking thread pool without blocking the Python event loop.

### Archive path traversal protection

All archive extraction functions (`zip::extract`, `tar_gz::extract_tar`, `tar_gz::extract_tar_gz`) validate that:
1. Entry paths contain no `..` or root components
2. Resolved output paths stay within the designated output directory

This prevents zip-slip attacks where a malicious archive writes files outside the target directory.

### Hashing

SHA-256 is used for content hashing because it provides collision resistance needed for deduplication. Files are read in 1MB chunks to avoid loading entire files into memory. The `hash_bytes` path is used for S3 objects (downloaded in full then hashed).

### Error handling

All Rust errors are collected into `FileError`, which implements `From` for `PyErr`. Each variant maps to the semantically appropriate Python exception (see `FileError` table above) — `?` propagation automatically produces the correct exception type at the PyO3 boundary.

## Usage Patterns

### Basic file operations

```python
import files_io

# Write and read
f = files_io.File("/tmp/output/variant_report.txt")
f.write("BRCA1 c.5266dupC - Pathogenic")
content = f.read(as_text=True)

# Check existence before overwriting
if f.exists():
    meta = f.metadata()
    print(f"File size: {meta['size']} bytes, last modified: {meta['mtime']}")

# Rename/move
f.rename("/tmp/archive/variant_report_v1.txt")
```

### Archive a results directory

```python
import files_io

# Compress a directory of analysis results
src_dir = "/data/results/run_20260507"
archive = "/data/archives/run_20260507.tar.gz"
count = files_io.File(src_dir).compress(archive, "tar.gz")
print(f"Compressed {count} files")

# Later, extract it
count = files_io.File(archive).extract("/data/restored/run_20260507")
print(f"Extracted {count} files")
```

### Batch copy with mixed local/S3 paths

```python
import files_io

sources = [
    "/data/variants/sample_001.vcf",
    "/data/variants/sample_002.vcf",
    "s3://bucket/raw/sample_003.vcf",
]
destinations = [
    "s3://bucket/processed/sample_001.vcf",
    "s3://bucket/processed/sample_002.vcf",
    "/data/local_backup/sample_003.vcf",
]

result = files_io.batch_copy(
    sources, destinations,
    access_key="AKIA...",
    secret_key="secret...",
    endpoint="http://minio:9000",
)
print(f"Copied: {result['success']}")
print(f"Failed: {result['failed']}")
```

### Async operations in an async context

```python
import asyncio
import files_io

async def process_files():
    f = files_io.File("/data/large_dataset/")
    # Compress without blocking the event loop
    count = await f.compress_async("/data/large_dataset.zip", "zip")
    print(f"Compressed {count} files")

    # Async batch copy
    result = await files_io.batch_copy_async(
        ["/data/a.txt", "/data/b.txt"],
        ["s3://bucket/a.txt", "s3://bucket/b.txt"],
        access_key="AKIA...",
        secret_key="secret...",
    )
    return result

asyncio.run(process_files())
```

### Content deduplication

```python
import files_io

# Build a set of known file hashes
paths = ["/data/file1.txt", "/data/file2.txt", "/data/file3.txt"]
result = files_io.batch_hash(paths)
known_hashes = list(result["hashes"].values())

# Check a new file against known content
new_file = "/data/incoming/file4.txt"
dup_result = files_io.check_duplicate(new_file, known_hashes)
if dup_result["is_duplicate"]:
    print(f"Duplicate found: {dup_result['hash']}")
else:
    print("New unique file")
```

## Extension Guide

### Adding a new backend

1. Create `src/backends/new_backend.rs` and implement the `FileOps` trait.
2. Add `pub mod new_backend;` to `src/backends/mod.rs`.
3. In `src/py/file.rs`, add a new variant to the `Backend` enum and update the `File::new()` constructor to detect the new path scheme.
4. Update `batch_copy` in `src/py/parallel.rs` to recognize the new scheme.

### Adding a new archive format

1. Create `src/archive/new_format.rs` with compress/extract functions following the existing pattern (validate inputs, guard against path traversal).
2. Register it in `src/archive/mod.rs`.
3. Add the format string to the `match` arms in `File::compress` and `File::extract` (in `src/py/file.rs`).

### Common pitfalls

- **S3 `rename` is not atomic.** It performs a copy-then-delete. If the delete fails, the copy is cleaned up, but there is a window where both objects exist.
- **`write_stream` for S3 buffers the entire input in memory** before uploading, because the S3 SDK needs a `ByteStream`. For large files, prefer the `write` method with a pre-loaded `bytes` object.
- **`content_hash` on S3 downloads the full object.** For large S3 files, consider hashing server-side (ETag) or pre-computing hashes on upload.
- **S3 `list_dir` uses delimiter-based listing.** It distinguishes common prefixes (pseudo-directories) from objects, but returns all entries as flat strings with the prefix stripped. S3 has no real directory hierarchy.

## Performance Notes

- **Hash chunk size:** 1 MB. Balances memory usage against syscall overhead for typical genomic data files.
- **`write_stream` buffer:** 1 MB for local writes. S3 writes buffer the full payload.
- **S3 shared runtime:** A single `tokio::runtime::Runtime` is shared across all `S3Backend` instances via `OnceLock`. This avoids the overhead of creating a new runtime per file operation.
- **Async variants** use `spawn_blocking` to offload I/O to the tokio blocking thread pool. This prevents blocking the Python async event loop but does not make the underlying I/O itself async -- the operations are still synchronous at the Rust level.
- **Archive compression** uses Deflate (zip) or default compression (tar.gz). No tuning knobs are exposed; for large archives, consider compressing in Python with chunked writes if memory is a concern.
- **S3 pagination:** `remove_dir_all` and `list_dir` handle S3 pagination via continuation tokens, so they work correctly for prefixes with more than 1000 objects.

## Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| `pyo3` | 0.28.2 | Rust-to-Python bindings (PyO3) |
| `pyo3-async-runtimes` | 0.28 | Async bridge between Python and tokio |
| `tokio` | 1 | Async runtime for S3 client and spawn_blocking |
| `aws-sdk-s3` | 1 | Amazon S3 client |
| `aws-config` | 1 | AWS SDK configuration |
| `aws-credential-types` | 1 | AWS credential types |
| `zip` | 2 | ZIP archive read/write |
| `tar` | 0.4 | TAR archive read/write |
| `flate2` | 1 | Gzip compression/decompression |
| `sha2` | 0.10 | SHA-256 hashing |
| `hex` | 0.4 | Hex encoding for hash digests |
| `serde` | 1 | Serialization (with `derive` feature) |
| `serde_json` | 1 | JSON serialization |
| `pythonize` | 0.28 | Convert Rust types to Python objects |
| `thiserror` | 2 | Derive `Error` trait for `FileError` |

Build system: [maturin](https://www.maturin.rs/) (>= 1.13). Requires Python >= 3.10, declared in `pyproject.toml`.

## Testing

Run the 14 Python integration tests with:

```bash
cd backend/libs/files-io
uv run pytest tests/test_files_io.py -v
```

Test coverage (Python, 14 tests):
- **Read/write:** bytes, text, context manager usage
- **Metadata:** dict structure, size, type flags
- **File operations:** exists, rename, copy, remove, remove_dir_all, list_dir
- **Content hashing:** same-content equality, different-content inequality
- **Archives:** zip compress/extract, tar.gz compress/extract
- **Deduplication:** check_duplicate, batch_hash

Run the 10 Rust tests with:

```bash
cd backend/libs/files-io
cargo test
```

Rust test coverage (10 tests):
- **Error mapping:** 5 tests verifying FileError → PyErr conversion (IO→IOError, Path→ValueError, Archive→ValueError, S3→ConnectionError, Other→RuntimeError)
- **Archive security:** 4 tests — zip symlink rejection, tar symlink rejection, tar.gz symlink rejection, zip path traversal through existing symlink parent (Unix-only)
- **Compatibility:** 1 test — legacy utility functions match expected behavior


Not covered by the current test suite:
- S3 backend (requires a running S3-compatible service)
- Async variants (copy_async, compress_async, extract_async, batch_copy_async)
- Error paths (invalid paths, permission denied, corrupt archives)
- read_chunk
- write_stream and ensure_dir (internal-only, marked #[allow(dead_code)])