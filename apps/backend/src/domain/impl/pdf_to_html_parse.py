# 将pdf解析为html 
from domain.abc.document_parser import DocumentParser
from utils.logger import Logger
from utils.exceptions import ParseException
from typing import Any
from infrastructure.adapters.mineru import MinerUInterface
import pdfplumber

class PDFToHTMLParser(DocumentParser):
    def __init__(self, mineru_adapter: MinerUInterface):
        self.mineru_adapter = mineru_adapter
        self.logger = Logger.get_logger("PDFToHTMLParser")
        self.logger.info("PDFToHTMLParser initialized with MinerU adapter")
    def parse(self, file_path: str) -> str:
        """Parse the PDF file and return its content as HTML string."""
        try:
            with pdfplumber.open(file_path) as pdf:
                html_content = ""
                for page in pdf.pages:
                    html_content += page.to_html()
            self.logger.info(f"Successfully parsed PDF file: {file_path}")
            return html_content
        except Exception as e:
            self.logger.error(f"Error parsing PDF file {file_path}: {e}")
            raise ParseException(f"Failed to parse PDF file: {e}")

    def validate(self, content: str) -> bool:
        """Validate the parsed HTML content."""
        if "<html>" in content and "</html>" in content:
            self.logger.info("Parsed content is valid HTML")
            return True
        else:
            self.logger.warning("Parsed content is not valid HTML")
            return False

    def save(self, content: str, destination: str) -> None:
        """Save the HTML content to the specified destination."""
        try:
            with open(destination, "w", encoding="utf-8") as f:
                f.write(content)
            self.logger.info(f"Successfully saved HTML content to: {destination}")
        except Exception as e:
            self.logger.error(f"Error saving HTML content to {destination}: {e}")
            raise ParseException(f"Failed to save HTML content: {e}")