# test document parser
import pytest
from domain.impl.pdf_parser import PDFParser
from infrastructure.adapters.mineru import MinerUImpl
from utils.exceptions import ParseException
@pytest.fixture
def mineru_adapter():
    return MinerUImpl()
@pytest.fixture
def pdf_parser(mineru_adapter):
    return PDFParser(mineru_adapter)
def test_parse_valid_pdf(pdf_parser, tmp_path):
    # 准备一个简单的PDF文件用于测试
    pdf_file = tmp_path / "test.pdf"
    with open(pdf_file, "wb") as f:
        f.write(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>\nendobj\n4 0 obj\n<< /Length 44 >>\nstream\nBT\n/F1 24 Tf\n100 700 Td\n(Hello, PDF!) Tj\nET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f \n0000000010 00000 n \n0000000061 00000 n \n0000000116 00000 n \n0000000211 00000 n \ntrailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n308\n%%EOF")
    # 调用解析方法
    html_content = pdf_parser.parse(str(pdf_file))
    # 验证解析结果
    assert "<html>" in html_content
    assert "Hello, PDF!" in html_content
def test_parse_invalid_pdf(pdf_parser, tmp_path):
    # 准备一个无效的PDF文件用于测试
    invalid_pdf_file = tmp_path / "invalid.pdf"
    with open(invalid_pdf_file, "wb") as f:
        f.write(b"This is not a valid PDF file.")
    # 调用解析方法并验证抛出异常
    with pytest.raises(ParseException):
        pdf_parser.parse(str(invalid_pdf_file))
def test_validate_html_content(pdf_parser):
    valid_html = "<html><body><h1>Test</h1></body></html>"
    invalid_html = "Just some text without HTML tags."
    assert pdf_parser.validate(valid_html) is True
    assert pdf_parser.validate(invalid_html) is False   
def test_validate_empty_content(pdf_parser):
    empty_content = ""
    assert pdf_parser.validate(empty_content) is False