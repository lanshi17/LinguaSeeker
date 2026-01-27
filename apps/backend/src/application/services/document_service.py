# 编排文件处理流程
from domain.__init__ import DocumentParser
from domain.impl.pdf_to_html_parse import PDFToHTMLParser
from infrastructure.adapters.mineru import MinerUAdapter
from utils.logger import Logger
from typing import Any
class DocumentService:
    """文档服务类，负责处理文档相关的业务逻辑"""

    def __init__(self):
        self.logger = Logger.get_logger("DocumentService")
        self.mineru_adapter = MinerUAdapter()
        self.pdf_parser: DocumentParser = PDFToHTMLParser(self.mineru_adapter)
        self.logger.info("DocumentService initialized")

    def process_pdf(self, file_path: str) -> str:
        """处理PDF文件并返回解析后的HTML内容"""
        try:
            self.logger.info(f"Processing PDF file: {file_path}")
            html_content = self.pdf_parser.parse(file_path)
            if not self.pdf_parser.validate(html_content):
                raise ValueError("Parsed content is not valid HTML")
            self.logger.info("PDF file processed successfully")
            return html_content
        except Exception as e:
            self.logger.error(f"Error processing PDF file: {e}")
            raise