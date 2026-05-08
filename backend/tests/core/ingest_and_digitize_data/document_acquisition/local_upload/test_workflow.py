"""Tests for local upload workflow."""

import tempfile
import os

from src.core.ingest_and_digitize_data.document_acquisition.local_upload.contracts import LocalUploadResult
from src.core.ingest_and_digitize_data.document_acquisition.local_upload.workflow import upload_document


class TestLocalUploadDocument:
    """Tests for upload_document workflow."""

    def test_successful_pdf_upload(self):
        content = b"%PDF-1.4 test content"
        result = upload_document(
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
        os.unlink(result.stored_file.file_path)

    def test_validation_failure_returns_error(self):
        result = upload_document(
            filename="test.exe",
            content=b"MZ executable",
            content_type="application/octet-stream",
        )
        assert result.success is False
        assert result.error is not None
        assert result.stored_file is None

    def test_empty_file_rejected(self):
        result = upload_document(
            filename="empty.pdf",
            content=b"",
            content_type="application/pdf",
        )
        assert result.success is False

    def test_upload_to_specific_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            content = b"%PDF-1.4 content for dir test"
            result = upload_document(
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
        result = upload_document(
            filename="report.docx",
            content=content,
        )
        assert result.success is True
        assert result.stored_file is not None
        os.unlink(result.stored_file.file_path)
