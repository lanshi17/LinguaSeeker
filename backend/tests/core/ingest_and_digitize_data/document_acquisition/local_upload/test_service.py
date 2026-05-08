"""Tests for local upload service."""

from src.core.ingest_and_digitize_data.document_acquisition.local_upload.contracts import (
    MAX_FILE_SIZE_BYTES,
    LocalUploadedFile,
)
from src.core.ingest_and_digitize_data.document_acquisition.local_upload.service import validate_local_upload


class TestValidateLocalUpload:
    """Tests for validate_local_upload function."""

    def test_valid_pdf_passes(self):
        content = b"%PDF-1.4 some content"
        uf = LocalUploadedFile(filename="test.pdf", content=content, content_type="application/pdf")
        errors = validate_local_upload(uf)
        assert errors == []

    def test_empty_file_rejected(self):
        uf = LocalUploadedFile(filename="empty.pdf", content=b"", content_type="application/pdf")
        errors = validate_local_upload(uf)
        assert any("empty" in e.lower() for e in errors)

    def test_oversized_file_rejected(self):
        big = b"x" * (MAX_FILE_SIZE_BYTES + 1)
        uf = LocalUploadedFile(filename="big.pdf", content=big, content_type="application/pdf")
        errors = validate_local_upload(uf)
        assert any("size" in e.lower() or "large" in e.lower() for e in errors)

    def test_invalid_extension_rejected(self):
        uf = LocalUploadedFile(filename="test.exe", content=b"MZ", content_type="application/octet-stream")
        errors = validate_local_upload(uf)
        assert any("extension" in e.lower() or "type" in e.lower() for e in errors)

    def test_doc_accepted(self):
        content = b"\xd0\xcf\x11\xe0 some doc content"
        uf = LocalUploadedFile(filename="test.doc", content=content, content_type="application/msword")
        errors = validate_local_upload(uf)
        assert errors == []

    def test_docx_accepted(self):
        content = b"PK\x03\x04 some docx content"
        uf = LocalUploadedFile(filename="test.docx", content=content)
        errors = validate_local_upload(uf)
        assert errors == []

    def test_pdf_without_magic_bytes_rejected(self):
        uf = LocalUploadedFile(
            filename="fake.pdf",
            content=b"not a real pdf file",
            content_type="application/pdf",
        )
        errors = validate_local_upload(uf)
        assert any("pdf" in e.lower() or "invalid" in e.lower() for e in errors)
