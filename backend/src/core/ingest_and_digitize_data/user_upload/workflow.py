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
