"""Public entry point for file upload."""

from __future__ import annotations

from typing import Optional

from loguru import logger

from .contracts import LocalUploadResult, LocalUploadedFile
from .service import store_local_file, validate_local_upload


def upload_document(
    filename: str,
    content: bytes,
    content_type: Optional[str] = None,
    upload_dir: Optional[str] = None,
) -> LocalUploadResult:
    """Upload a file: validate, hash, and store.

    Args:
        filename: Original filename from the user.
        content: Raw file bytes.
        content_type: MIME type (optional).
        upload_dir: Directory to store files. None = system temp dir.

    Returns:
        LocalUploadResult with stored file info or error.
    """
    uploaded = LocalUploadedFile(
        filename=filename,
        content=content,
        content_type=content_type,
    )

    errors = validate_local_upload(uploaded)
    if errors:
        logger.warning("Upload validation failed for {}: {}", filename, errors)
        return LocalUploadResult(
            success=False,
            error="; ".join(errors),
            warnings=errors,
        )

    try:
        stored = store_local_file(uploaded, upload_dir=upload_dir)
        return LocalUploadResult(success=True, stored_file=stored)
    except Exception as exc:
        logger.error("Failed to store file {}: {}", filename, exc)
        return LocalUploadResult(success=False, error=str(exc))
