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
