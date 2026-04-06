# test document parser
import pytest
from unittest.mock import Mock
from src.domain.impl.pdf_parser import PDFParser
from src.infrastructure.adapters.mineru import MinerUAdapterImpl
from src.utils.exceptions import ParseException


@pytest.fixture
def mock_mineru_adapter():
    """Create a mock MinerU adapter for testing"""
    mock_adapter = Mock(spec=MinerUAdapterImpl)

    # Mock the mineru_parse method (new unified API)
    mock_adapter.mineru_parse.return_value = {
        "file_id": "test_file_id",
        "file_name": "test.pdf",
        "state": "completed",
        "full_zip_url": "https://example.com/result.zip"
    }

    return mock_adapter


@pytest.fixture
def pdf_parser(mock_mineru_adapter):
    return PDFParser(mock_mineru_adapter)

def test_parse_valid_pdf(pdf_parser, mock_mineru_adapter, tmp_path):
    # 准备一个简单的PDF文件用于测试
    pdf_file = tmp_path / "test.pdf"
    with open(pdf_file, "wb") as f:
        f.write(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")

    # Call the parse method
    result = pdf_parser.parse(str(pdf_file))

    # Verify the parse result
    assert result["file_id"] == "test_file_id"
    assert result["state"] == "completed"
    assert result["full_zip_url"] == "https://example.com/result.zip"

    # Verify the adapter was called
    mock_mineru_adapter.mineru_parse.assert_called_once()


def test_parse_invalid_pdf(pdf_parser, mock_mineru_adapter, tmp_path):
    """Test that parsing fails with invalid PDF"""
    # Prepare an invalid PDF file for testing
    invalid_pdf_file = tmp_path / "invalid.pdf"
    with open(invalid_pdf_file, "wb") as f:
        f.write(b"This is not a valid PDF file.")

    # Call the parse method and verify exception is raised
    with pytest.raises(ParseException):
        pdf_parser.parse(str(invalid_pdf_file))



def test_validate_empty_content(pdf_parser):
    """Test validation of empty content"""
    empty_content = ""
    assert pdf_parser.validate(empty_content) is False