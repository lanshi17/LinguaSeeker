"""File upload validation and storage service."""

from __future__ import annotations

import hashlib
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
    from rust_io import files as rust_files
except ImportError:
    rust_files = None  # type: ignore[assignment]
    logger.warning("rust_io.files not available, falling back to Python I/O")


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
    """Compute SHA-256 hash of data (Python fallback)."""
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

    if upload_dir:
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, f"{_compute_sha256(file.content)}{ext}")
    else:
        file_path = _write_to_temp(file.content, suffix=ext)

    # Write file (skip for temp path — already written by _write_to_temp)
    if upload_dir:
        if rust_files is not None:
            rust_files.write_file(file_path, file.content)
        else:
            with open(file_path, "wb") as f:
                f.write(file.content)

    # Hash: verify from disk when Rust is available, else from memory
    if rust_files is not None:
        verified_hash = rust_files.compute_sha256(file_path)
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
