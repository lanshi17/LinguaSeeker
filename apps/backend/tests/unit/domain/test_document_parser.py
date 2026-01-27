# test document parser
import pytest
from domain.impl.pdf_parser import PDFParser
from infrastructure.adapters.mineru import MinerUImpl
from utils.exceptions import ParseException


@pytest.fixture
def mock_mineru_adapter():
    """Create a mock MinerU adapter for testing"""
    mock_adapter = Mock(spec=MinerUImpl)
    
    # Mock the pipeline processing flow
    mock_adapter.pipline_process.return_value = {
        "test_file_id": {
            "extract_result": {
                "state": "completed",
                "full_zip_url": "https://example.com/result.zip"
            }
        }
    }
    
    mock_adapter.get_processing_status.return_value = {
        "extract_result": {
            "state": "completed"
        }
    }
    
    mock_adapter.retrieve_results.return_value = {
        "extract_result": {
            "state": "completed",
            "full_zip_url": "https://example.com/result.zip"
        }
    }
    
    return mock_adapter


@pytest.fixture
def pdf_parser(mock_mineru_adapter):
    return PDFParser(mock_mineru_adapter)

def test_parse_valid_pdf(pdf_parser, tmp_path):
    # 准备一个简单的PDF文件用于测试
    pdf_file = tmp_path / "test.pdf"
    with open(pdf_file, "wb") as f:
        f.write(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    
    # Create a mock zip file with HTML content
    zip_path = tmp_path / "result.zip"
    html_content = "<html><body><h1>Hello, PDF!</h1></body></html>"
    
    with zipfile.ZipFile(zip_path, 'w') as zf:
        zf.writestr("result.html", html_content)
    
    # Mock the download_file function to return the zip we created
    with patch('domain.impl.pdf_to_html_parse.download_file') as mock_download:
        # Mock download to copy our test zip
        def mock_download_side_effect(url, destination):
            import shutil
            shutil.copy(str(zip_path), destination)
            return destination
        
        mock_download.side_effect = mock_download_side_effect
        
        # Call the parse method
        result = pdf_parser.parse(str(pdf_file))
        
        # Verify the parse result
        assert "<html>" in result
        assert "Hello, PDF!" in result
        
        # Verify the adapter was called
        mock_mineru_adapter.pipline_process.assert_called_once_with([str(pdf_file)])


def test_parse_invalid_pdf(pdf_parser, mock_mineru_adapter, tmp_path):
    """Test that parsing fails with invalid PDF"""
    # Mock a failure in the pipeline
    mock_mineru_adapter.pipline_process.return_value = {}
    
    # Prepare an invalid PDF file for testing
    invalid_pdf_file = tmp_path / "invalid.pdf"
    with open(invalid_pdf_file, "wb") as f:
        f.write(b"This is not a valid PDF file.")
    
    # Call the parse method and verify exception is raised
    with pytest.raises(ParseException):
        pdf_parser.parse(str(invalid_pdf_file))


def test_validate_html_content(pdf_parser):
    """Test HTML content validation"""
    valid_html = "<html><body><h1>Test</h1></body></html>"
    invalid_html = "Just some text without HTML tags."
    assert pdf_parser.validate(valid_html) is True
    assert pdf_parser.validate(invalid_html) is False


def test_validate_empty_content(pdf_parser):
    """Test validation of empty content"""
    empty_content = ""
    assert pdf_parser.validate(empty_content) is False
