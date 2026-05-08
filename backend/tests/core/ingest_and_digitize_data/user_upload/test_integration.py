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
