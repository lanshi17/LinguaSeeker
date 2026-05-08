# User Upload Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement file upload module at `src/core/ingest_and_digitize_data/user_upload/` supporting PDF upload with file validation, hash computation, and local filesystem storage. I/O heavy operations delegated to `libs/files-io/` (Rust PyO3).

**Architecture:** Three-layer design: `contracts.py` (data types) -> `service.py` (business logic) -> `workflow.py` (public entry point). Rust `files-io` handles file I/O (write, hash, validate). Python layer orchestrates. Local filesystem storage with temp directory. No API routes, no DB, no Celery — pure module with callable interface.

**Tech Stack:** Python 3.12, FastAPI (UploadFile type only), Pydantic, Rust/PyO3 (`files-io`), `loguru`

---

## Task 1: Add file I/O functions to `files-io` (Rust)

**Files:**
- Modify: `libs/files-io/Cargo.toml`
- Modify: `libs/files-io/src/lib.rs`

**Step 1: Write Rust functions for file I/O**

Add dependencies to `Cargo.toml` and implement three functions in `lib.rs`:
- `compute_sha256(file_path: &str) -> PyResult<String>` — compute SHA-256 hash of a file
- `write_file(file_path: &str, data: &[u8]) -> PyResult<()>` — write bytes to file
- `validate_pdf_magic(data: &[u8]) -> PyResult<bool>` — check if bytes start with `%PDF`

```toml
# Cargo.toml additions
[dependencies]
pyo3 = { version = "0.28.2", features = ["extension-module"] }
sha2 = "0.10"
```

```rust
// lib.rs
use pyo3::prelude::*;
use sha2::{Sha256, Digest};
use std::io::Write;

#[pymodule]
fn files_io(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(compute_sha256, m)?)?;
    m.add_function(wrap_pyfunction!(write_file, m)?)?;
    m.add_function(wrap_pyfunction!(validate_pdf_magic, m)?)?;
    Ok(())
}

#[pyfunction]
fn compute_sha256(file_path: &str) -> PyResult<String> {
    let data = std::fs::read(file_path)
        .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))?;
    let mut hasher = Sha256::new();
    hasher.update(&data);
    Ok(format!("{:x}", hasher.finalize()))
}

#[pyfunction]
fn write_file(file_path: &str, data: &[u8]) -> PyResult<()> {
    let mut file = std::fs::File::create(file_path)
        .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))?;
    file.write_all(data)
        .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))?;
    Ok(())
}

#[pyfunction]
fn validate_pdf_magic(data: &[u8]) -> PyResult<bool> {
    Ok(data.len() >= 4 && &data[..4] == b"%PDF")
}
```

**Step 2: Build and verify**

```bash
cd libs/files-io
maturin develop --release
python -c "import files_io; print(files_io.validate_pdf_magic(b'%PDF-1.4'))"
```

Expected: `True`

**Step 3: Commit**

```bash
git add libs/files-io/Cargo.toml libs/files-io/src/lib.rs
git commit -m "feat(files-io): add compute_sha256, write_file, validate_pdf_magic"
```

---

## Task 2: Create contracts (data types)

**Files:**
- Create: `src/core/ingest_and_digitize_data/user_upload/__init__.py`
- Create: `src/core/ingest_and_digitize_data/user_upload/contracts.py`

**Step 1: Write the contracts**

```python
# contracts.py
"""Data types for user file upload."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

# Allowed MIME types
ALLOWED_CONTENT_TYPES = frozenset({
    "application/pdf",
    "application/msword",  # .doc
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
})

# Allowed file extensions
ALLOWED_EXTENSIONS = frozenset({".pdf", ".doc", ".docx"})

# Max file size: 50MB
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024


@dataclass(frozen=True)
class UploadedFile:
    """Represents a validated uploaded file."""
    filename: str
    content: bytes
    content_type: Optional[str] = None
    size: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "size", len(self.content))


@dataclass(frozen=True)
class StoredFile:
    """Result of storing a file to disk."""
    file_path: str
    sha256: str
    original_filename: str
    size: int
    content_type: Optional[str] = None


@dataclass
class UploadResult:
    """Final upload result returned to caller."""
    success: bool
    stored_file: Optional[StoredFile] = None
    warnings: List[str] = field(default_factory=list)
    error: Optional[str] = None
```

**Step 2: Verify imports**

```bash
cd /data/yangzs/Projects/01_ACMG_Lingua/backend
python -c "from src.core.ingest_and_digitize_data.user_upload.contracts import UploadResult; print('OK')"
```

Expected: `OK`

**Step 3: Commit**

```bash
git add src/core/ingest_and_digitize_data/user_upload/__init__.py src/core/ingest_and_digitize_data/user_upload/contracts.py
git commit -m "feat(user-upload): add contracts with UploadedFile, StoredFile, UploadResult"
```

---

## Task 3: Create file validation service

**Files:**
- Create: `src/core/ingest_and_digitize_data/user_upload/service.py`

**Step 1: Write failing test**

```bash
mkdir -p tests/core/ingest_and_digitize_data/user_upload
touch tests/core/ingest_and_digitize_data/user_upload/__init__.py
```

```python
# tests/core/ingest_and_digitize_data/user_upload/test_service.py
"""Tests for user upload service."""

import pytest
from pathlib import Path

from src.core.ingest_and_digitize_data.user_upload.contracts import (
    MAX_FILE_SIZE_BYTES,
    UploadedFile,
)
from src.core.ingest_and_digitize_data.user_upload.service import validate_upload


class TestValidateUpload:
    """Tests for validate_upload function."""

    def test_valid_pdf_passes(self):
        content = b"%PDF-1.4 some content"
        uf = UploadedFile(filename="test.pdf", content=content, content_type="application/pdf")
        errors = validate_upload(uf)
        assert errors == []

    def test_empty_file_rejected(self):
        uf = UploadedFile(filename="empty.pdf", content=b"", content_type="application/pdf")
        errors = validate_upload(uf)
        assert any("empty" in e.lower() for e in errors)

    def test_oversized_file_rejected(self):
        big = b"x" * (MAX_FILE_SIZE_BYTES + 1)
        uf = UploadedFile(filename="big.pdf", content=big, content_type="application/pdf")
        errors = validate_upload(uf)
        assert any("size" in e.lower() or "large" in e.lower() for e in errors)

    def test_invalid_extension_rejected(self):
        uf = UploadedFile(filename="test.exe", content=b"MZ", content_type="application/octet-stream")
        errors = validate_upload(uf)
        assert any("extension" in e.lower() or "type" in e.lower() for e in errors)

    def test_doc_accepted(self):
        content = b"\xd0\xcf\x11\xe0 some doc content"
        uf = UploadedFile(filename="test.doc", content=content, content_type="application/msword")
        errors = validate_upload(uf)
        assert errors == []

    def test_docx_accepted(self):
        content = b"PK\x03\x04 some docx content"
        uf = UploadedFile(filename="test.docx", content=content)
        errors = validate_upload(uf)
        assert errors == []
```

**Step 2: Run test to verify it fails**

```bash
cd /data/yangzs/Projects/01_ACMG_Lingua/backend
uv run pytest tests/core/ingest_and_digitize_data/user_upload/test_service.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'src.core.ingest_and_digitize_data.user_upload.service'`

**Step 3: Implement validate_upload**

```python
# src/core/ingest_and_digitize_data/user_upload/service.py
"""File upload validation and storage service."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import List, Optional

from loguru import logger

from .contracts import (
    ALLOWED_EXTENSIONS,
    MAX_FILE_SIZE_BYTES,
    StoredFile,
    UploadedFile,
)

try:
    import files_io
except ImportError:
    files_io = None  # type: ignore[assignment]
    logger.warning("files_io not available, falling back to Python I/O")

import hashlib


def validate_upload(file: UploadedFile) -> List[str]:
    """Validate an uploaded file. Returns list of error messages (empty = valid)."""
    errors: List[str] = []

    if not file.content:
        errors.append("File is empty")
        return errors

    if file.size > MAX_FILE_SIZE_BYTES:
        errors.append(f"File too large: {file.size} bytes (max {MAX_FILE_SIZE_BYTES})")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        errors.append(f"Unsupported file extension: {ext}. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}")

    return errors


def _compute_sha256(data: bytes) -> str:
    """Compute SHA-256 hash of data."""
    return hashlib.sha256(data).hexdigest()


def _write_to_temp(data: bytes, suffix: str) -> str:
    """Write bytes to a temporary file, return path."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)
    return path


def store_file(
    file: UploadedFile,
    upload_dir: Optional[str] = None,
) -> StoredFile:
    """Validate, hash, and store an uploaded file.

    Args:
        file: The uploaded file to store.
        upload_dir: Directory to store files in. Defaults to system temp dir.

    Returns:
        StoredFile with path, hash, and metadata.

    Raises:
        ValueError: If validation fails.
    """
    errors = validate_upload(file)
    if errors:
        raise ValueError(f"Validation failed: {'; '.join(errors)}")

    ext = Path(file.filename).suffix.lower()
    sha256 = _compute_sha256(file.content)

    # Determine storage directory
    if upload_dir:
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, f"{sha256}{ext}")
    else:
        file_path = _write_to_temp(file.content, suffix=ext)

    # Write file using Rust I/O if available
    if files_io is not None and upload_dir:
        files_io.write_file(file_path, file.content)
    elif not upload_dir:
        # Already written by _write_to_temp
        pass
    else:
        with open(file_path, "wb") as f:
            f.write(file.content)

    # Compute hash via Rust if available
    if files_io is not None and upload_dir:
        verified_hash = files_io.compute_sha256(file_path)
    else:
        verified_hash = _compute_sha256(file.content)

    logger.info(
        "Stored file: {} -> {} (sha256={}, size={})",
        file.filename,
        file_path,
        verified_hash[:16],
        file.size,
    )

    return StoredFile(
        file_path=file_path,
        sha256=verified_hash,
        original_filename=file.filename,
        size=file.size,
        content_type=file.content_type,
    )
```

**Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/core/ingest_and_digitize_data/user_upload/test_service.py -v
```

Expected: All PASS

**Step 5: Commit**

```bash
git add src/core/ingest_and_digitize_data/user_upload/service.py tests/core/ingest_and_digitize_data/user_upload/
git commit -m "feat(user-upload): add validate_upload and store_file service"
```

---

## Task 4: Create workflow (public entry point)

**Files:**
- Create: `src/core/ingest_and_digitize_data/user_upload/workflow.py`

**Step 1: Write failing test**

```python
# tests/core/ingest_and_digitize_data/user_upload/test_workflow.py
"""Tests for user upload workflow."""

import pytest
import tempfile
import os

from src.core.ingest_and_digitize_data.user_upload.contracts import UploadResult
from src.core.ingest_and_digitize_data.user_upload.workflow import upload_file


class TestUploadFile:
    """Tests for upload_file workflow."""

    def test_successful_pdf_upload(self):
        content = b"%PDF-1.4 test content"
        result = upload_file(
            filename="test.pdf",
            content=content,
            content_type="application/pdf",
        )
        assert result.success is True
        assert result.stored_file is not None
        assert result.stored_file.original_filename == "test.pdf"
        assert result.stored_file.sha256
        assert result.stored_file.size == len(content)
        assert os.path.exists(result.stored_file.file_path)
        # Cleanup
        os.unlink(result.stored_file.file_path)

    def test_validation_failure_returns_error(self):
        result = upload_file(
            filename="test.exe",
            content=b"MZ executable",
            content_type="application/octet-stream",
        )
        assert result.success is False
        assert result.error is not None
        assert result.stored_file is None

    def test_empty_file_rejected(self):
        result = upload_file(
            filename="empty.pdf",
            content=b"",
            content_type="application/pdf",
        )
        assert result.success is False

    def test_upload_to_specific_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            content = b"%PDF-1.4 content for dir test"
            result = upload_file(
                filename="dir_test.pdf",
                content=content,
                content_type="application/pdf",
                upload_dir=tmpdir,
            )
            assert result.success is True
            assert result.stored_file is not None
            assert result.stored_file.file_path.startswith(tmpdir)
            assert os.path.exists(result.stored_file.file_path)

    def test_docx_upload(self):
        content = b"PK\x03\x04 docx content here"
        result = upload_file(
            filename="report.docx",
            content=content,
        )
        assert result.success is True
        assert result.stored_file is not None
        os.unlink(result.stored_file.file_path)
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/core/ingest_and_digitize_data/user_upload/test_workflow.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'src.core.ingest_and_digitize_data.user_upload.workflow'`

**Step 3: Implement workflow**

```python
# src/core/ingest_and_digitize_data/user_upload/workflow.py
"""Public entry point for file upload."""

from __future__ import annotations

from typing import Optional

from loguru import logger

from .contracts import UploadResult, UploadedFile
from .service import store_file, validate_upload


def upload_file(
    filename: str,
    content: bytes,
    content_type: Optional[str] = None,
    upload_dir: Optional[str] = None,
) -> UploadResult:
    """Upload a file: validate, hash, and store.

    Args:
        filename: Original filename from the user.
        content: Raw file bytes.
        content_type: MIME type (optional).
        upload_dir: Directory to store files. None = system temp dir.

    Returns:
        UploadResult with stored file info or error.
    """
    uploaded = UploadedFile(
        filename=filename,
        content=content,
        content_type=content_type,
    )

    errors = validate_upload(uploaded)
    if errors:
        logger.warning("Upload validation failed for {}: {}", filename, errors)
        return UploadResult(
            success=False,
            error="; ".join(errors),
            warnings=errors,
        )

    try:
        stored = store_file(uploaded, upload_dir=upload_dir)
        return UploadResult(success=True, stored_file=stored)
    except Exception as exc:
        logger.error("Failed to store file {}: {}", filename, exc)
        return UploadResult(success=False, error=str(exc))
```

**Step 4: Run all tests**

```bash
uv run pytest tests/core/ingest_and_digitize_data/user_upload/ -v
```

Expected: All PASS

**Step 5: Commit**

```bash
git add src/core/ingest_and_digitize_data/user_upload/workflow.py tests/core/ingest_and_digitize_data/user_upload/test_workflow.py
git commit -m "feat(user-upload): add workflow entry point with upload_file"
```

---

## Task 5: Add PDF magic validation to service (uses files_io)

**Files:**
- Modify: `src/core/ingest_and_digitize_data/user_upload/service.py`
- Modify: `tests/core/ingest_and_digitize_data/user_upload/test_service.py`

**Step 1: Add failing test for PDF magic validation**

```python
# Add to test_service.py
    def test_pdf_without_magic_bytes_rejected(self):
        uf = UploadedFile(
            filename="fake.pdf",
            content=b"not a real pdf file",
            content_type="application/pdf",
        )
        errors = validate_upload(uf)
        assert any("pdf" in e.lower() or "invalid" in e.lower() for e in errors)
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/core/ingest_and_digitize_data/user_upload/test_service.py::TestValidateUpload::test_pdf_without_magic_bytes_rejected -v
```

Expected: FAIL — `AssertionError`

**Step 3: Add PDF magic validation to service**

In `validate_upload`, add after extension check:

```python
    # Validate PDF magic bytes
    if ext == ".pdf":
        if files_io is not None:
            if not files_io.validate_pdf_magic(file.content):
                errors.append("Invalid PDF: missing %PDF magic bytes")
        elif not file.content[:4] == b"%PDF":
            errors.append("Invalid PDF: missing %PDF magic bytes")
```

**Step 4: Run tests**

```bash
uv run pytest tests/core/ingest_and_digitize_data/user_upload/ -v
```

Expected: All PASS

**Step 5: Commit**

```bash
git add src/core/ingest_and_digitize_data/user_upload/service.py tests/core/ingest_and_digitize_data/user_upload/test_service.py
git commit -m "feat(user-upload): add PDF magic byte validation via files_io"
```

---

## Task 6: Update `__init__.py` with public API

**Files:**
- Modify: `src/core/ingest_and_digitize_data/user_upload/__init__.py`

**Step 1: Export public interface**

```python
# src/core/ingest_and_digitize_data/user_upload/__init__.py
"""User file upload module."""

from .contracts import UploadResult, UploadedFile, StoredFile
from .workflow import upload_file
from .service import validate_upload, store_file

__all__ = [
    "UploadResult",
    "UploadedFile",
    "StoredFile",
    "upload_file",
    "validate_upload",
    "store_file",
]
```

**Step 2: Verify imports**

```bash
python -c "from src.core.ingest_and_digitize_data.user_upload import upload_file, UploadResult; print('OK')"
```

Expected: `OK`

**Step 3: Commit**

```bash
git add src/core/ingest_and_digitize_data/user_upload/__init__.py
git commit -m "feat(user-upload): export public API from __init__"
```

---

## Task 7: Final integration test

**Files:**
- Create: `tests/core/ingest_and_digitize_data/user_upload/test_integration.py`

**Step 1: Write integration test**

```python
# tests/core/ingest_and_digitize_data/user_upload/test_integration.py
"""Integration tests for user upload end-to-end flow."""

import os
import tempfile

from src.core.ingest_and_digitize_data.user_upload import upload_file


def test_full_upload_flow():
    """Test complete upload: validate -> hash -> store -> verify."""
    pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n"

    with tempfile.TemporaryDirectory() as tmpdir:
        result = upload_file(
            filename="variant_report.pdf",
            content=pdf_content,
            content_type="application/pdf",
            upload_dir=tmpdir,
        )

        assert result.success is True
        assert result.stored_file is not None
        assert result.stored_file.original_filename == "variant_report.pdf"
        assert len(result.stored_file.sha256) == 64  # SHA-256 hex length
        assert result.stored_file.size == len(pdf_content)
        assert result.stored_file.file_path.startswith(tmpdir)

        # Verify file content on disk matches
        with open(result.stored_file.file_path, "rb") as f:
            assert f.read() == pdf_content


def test_upload_without_dir():
    """Test upload to temp directory."""
    result = upload_file(
        filename="temp_test.pdf",
        content=b"%PDF-1.4 temp",
        content_type="application/pdf",
    )
    assert result.success is True
    assert result.stored_file is not None
    assert os.path.exists(result.stored_file.file_path)
    os.unlink(result.stored_file.file_path)
```

**Step 2: Run all tests**

```bash
uv run pytest tests/core/ingest_and_digitize_data/user_upload/ -v
```

Expected: All PASS

**Step 3: Commit**

```bash
git add tests/core/ingest_and_digitize_data/user_upload/test_integration.py
git commit -m "test(user-upload): add integration tests for full upload flow"
```

---

## Final Verification

```bash
# Run all user_upload tests
uv run pytest tests/core/ingest_and_digitize_data/user_upload/ -v

# Lint
uv run ruff check src/core/ingest_and_digitize_data/user_upload/

# Verify module structure
find src/core/ingest_and_digitize_data/user_upload/ -type f -name "*.py"
```

Expected structure:
```
src/core/ingest_and_digitize_data/user_upload/
    __init__.py
    contracts.py
    service.py
    workflow.py
```

---

## Summary

| Task | What | Rust/Python |
|------|------|-------------|
| 1 | `files-io` I/O functions | Rust |
| 2 | Contracts (data types) | Python |
| 3 | Validation + storage service | Python (calls Rust) |
| 4 | Workflow entry point | Python |
| 5 | PDF magic validation | Python (calls Rust) |
| 6 | Public API exports | Python |
| 7 | Integration tests | Python |
