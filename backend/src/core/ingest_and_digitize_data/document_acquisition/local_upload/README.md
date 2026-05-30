# Local Upload Module

> Phase 1 submodule — validates, hashes, and stores user-uploaded files (PDF/DOC/DOCX) to local disk.

## Quick Start

```python
from src.core.ingest_and_digitize_data.document_acquisition.local_upload import (
    upload_document,
    LocalUploadResult,
)

result: LocalUploadResult = upload_document(
    filename="study.pdf",
    content=pdf_bytes,
    content_type="application/pdf",
    upload_dir="/data/uploads",
)
if result.success:
    print(f"Stored: {result.stored_file.sha256}")
```

## Architecture

```
upload_document() [workflow.py]  ← public entry point
    │
    ├─ validate_local_upload() [service.py]
    │      ├─ empty check
    │      ├─ size limit (50 MB)
    │      ├─ extension whitelist (.pdf, .doc, .docx)
    │      └─ PDF magic bytes (%PDF)
    │
    └─ store_local_file() [service.py]
           ├─ hash via SHA-256 (Rust files-io if available, else stdlib)
           ├─ write to disk (files-io.File or stdlib open)
           └─ return LocalStoredFile with path + metadata
```

All functions are **synchronous** — this module runs during HTTP request handling in FastAPI, blocking is acceptable for small (~MB) files.

## Public API

### `upload_document()`

```python
def upload_document(
    filename: str,
    content: bytes,
    content_type: str | None = None,
    upload_dir: str | None = None,
) -> LocalUploadResult:
```

Validates, hashes, and stores a file. Returns `LocalUploadResult.success=False` (not an exception) on validation failures; raises only on unexpected disk errors.

### Data Types

| Type | Kind | Description |
|------|------|-------------|
| `LocalUploadedFile` | `frozen dataclass` | Raw uploaded file (filename, content bytes, content_type) |
| `LocalStoredFile` | `frozen dataclass` | Stored file metadata (path, sha256, original name, size) |
| `LocalUploadResult` | `mutable dataclass` | Result wrapper (success, stored_file, warnings, error) |

### Constants

| Constant | Value | Purpose |
|----------|-------|---------|
| `ALLOWED_EXTENSIONS` | `{".pdf", ".doc", ".docx"}` | Whitelist |
| `MAX_FILE_SIZE_BYTES` | `52,428,800` (50 MB) | Size cap |

## Internal Design

### Dual-path I/O strategy

The module tries Rust `files-io` first, falls back to Python stdlib:

```
if files_io is not None:          # PyO3 extension available
    files_io.File(path).write(content)
    files_io.File(path).content_hash()
else:                              # stdlib fallback
    open(path, "wb").write(content)
    hashlib.sha256(content).hexdigest()
```

The hash is always **verified from disk** when Rust is available (re-read + hash), providing integrity verification. With stdlib fallback, the hash is computed from memory bytes.

### Validation rules

1. Non-empty file (bytes > 0)
2. Size ≤ 50 MB
3. Extension in whitelist (case-insensitive)
4. PDF files: first 4 bytes must be `%PDF` (magic bytes)

Validation errors are returned as a `list[str]` — never raised as exceptions for normal validation failures.

### Temp file strategy

When `upload_dir` is `None`, files are written to system temp via `tempfile.mkstemp()`. Files in system temp are **not automatically cleaned up** — callers should track and remove them.

## Usage Patterns

### Basic upload with validation

```python
from src.core.ingest_and_digitize_data.document_acquisition.local_upload import (
    upload_document,
)

result = upload_document("paper.pdf", file_bytes)
if not result.success:
    print(f"Validation failed: {result.error}")
    return
# result.stored_file.sha256 is ready for dedup checks
```

### Store to a specific directory

```python
result = upload_document(
    "thesis.docx",
    docx_bytes,
    upload_dir="/app/data/documents",
)
# File is named <sha256>.docx in /app/data/documents
```

### Integration with FastAPI endpoint

```python
@router.post("/upload")
async def upload(file: UploadFile = File(...)):
    content = await file.read()
    result = upload_document(
        filename=file.filename,
        content=content,
        content_type=file.content_type,
        upload_dir=settings.upload_dir,
    )
    if not result.success:
        raise HTTPException(400, detail=result.error)
    return {"sha256": result.stored_file.sha256}
```

## Extension Guide

### Adding a new file format

1. Add the extension to `ALLOWED_EXTENSIONS` in `contracts.py`
2. Optionally add magic-byte validation in `validate_local_upload()`:

```python
if ext == ".docx" and not file.content[:2] == b"PK":
    errors.append("Invalid DOCX: missing ZIP magic bytes")
```

### Adding a new validation rule

Add to `validate_local_upload()` in `service.py`. Return error strings — don't raise for validation failures:

```python
def validate_local_upload(file: LocalUploadedFile) -> list[str]:
    errors = []
    # ... existing checks ...
    if b"malicious_pattern" in file.content[:1024]:
        errors.append("File contains blocked content")
    return errors
```

### Adding cloud storage (S3)

This module is intentionally local-only. For S3, extend the parent module (`document_acquisition/service.py`) to branch on storage backend — don't modify local_upload to handle both.

## Performance Notes

- Validation runs in ~0.1 ms (checks file size + first 4 bytes only)
- SHA-256 is ~50 MB/s on modern CPUs with Rust; ~100 MB/s with Python stdlib
- 50 MB cap prevents memory exhaustion from a single upload
- Sync I/O is acceptable because uploads complete within the HTTP request/response cycle

## Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| `loguru` | Project | Structured logging |
| `src.utils.rust_io.files_io` | Project | Optional Rust-native I/O + hashing |
| `hashlib` | stdlib | SHA-256 fallback |
| `tempfile` | stdlib | Temp file creation |
| `os` / `pathlib` | stdlib | Path manipulation |

## Testing

```bash
uv run pytest tests/ -k "local_upload" -v
```

No dedicated test file yet. Coverage: validation rules and store path are exercised indirectly through the document acquisition integration tests.
