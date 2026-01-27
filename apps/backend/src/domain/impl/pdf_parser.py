# 将pdf解析为html
from domain.abc.document_parser import DocumentParser
from utils.logger import Logger
from utils.exceptions import ParseException
from utils.detect_langguage import detect_language
from typing import Any, Dict, Optional
from infrastructure.adapters.mineru import MinerUInterface
import pdfplumber
import time

class PDFParser(DocumentParser):
    def __init__(self, mineru_adapter: MinerUInterface):
        self.mineru_adapter = mineru_adapter
        self.logger = Logger.get_logger("PDFParser")
        self.logger.info("PDFParser initialized with MinerU adapter")

    def parse_with_mineru(self, file_path: str, document_id: Optional[str] = None) -> Dict[str, Any]:
        """使用MinerU解析PDF文件,包含语言检测

        Args:
            file_path: PDF文件路径
            document_id: 文档唯一标识符(可选)

        Returns:
            包含file_id、full_zip_url等信息的字典
        """
        try:
            self.logger.info(f"Starting MinerU processing for: {file_path}")

            # 步骤1: 使用pdfplumber提取文本进行语言检测
            text_sample = self._extract_text_sample(file_path, max_chars=1000)
            detected_languages = detect_language(text_sample)
            self.logger.info(f"Detected languages: {detected_languages}")

            # 步骤2: 申请上传URL,配置语言参数
            file_config = {
                file_path: {
                    "parse_language": detected_languages
                }
            }
            upload_response = self.mineru_adapter.apply_upload_urls([file_path], file_config)
            file_info = upload_response.get("files", [])[0]
            file_id = file_info.get("file_id")
            upload_url = file_info.get("upload_url")

            if not file_id or not upload_url:
                raise ParseException("Failed to get upload URL from MinerU")

            self.logger.info(f"Received file_id: {file_id}")

            # 步骤3: 上传文件到MinerU
            self.mineru_adapter.upload_to_urls([file_path], [upload_url])
            self.logger.info("File uploaded to MinerU successfully")

            # 步骤4: 轮询检查处理状态
            max_wait_time = 300  # 最多等待5分钟
            poll_interval = 5  # 每5秒检查一次
            elapsed_time = 0

            while elapsed_time < max_wait_time:
                status_response = self.mineru_adapter.get_processing_status(file_id)
                extract_result = status_response.get("extract_result", {})
                state = extract_result.get("state")

                if state == "completed":
                    self.logger.info("MinerU processing completed successfully")
                    result_response = self.mineru_adapter.retrieve_results(file_id)
                    extract_result = result_response.get("extract_result", {})

                    return {
                        "file_id": file_id,
                        "full_zip_url": extract_result.get("full_zip_url"),
                        "file_name": extract_result.get("file_name"),
                        "state": state,
                        "detected_languages": detected_languages,
                        "document_id": document_id
                    }

                elif state == "failed":
                    error_msg = extract_result.get("err_msg", "Unknown error")
                    raise ParseException(f"MinerU processing failed: {error_msg}")

                elif state == "running":
                    progress = extract_result.get("extract_progress", {})
                    self.logger.info(
                        f"Processing in progress: {progress.get('extracted_pages')}/{progress.get('total_pages')} pages"
                    )

                time.sleep(poll_interval)
                elapsed_time += poll_interval

            raise ParseException(f"MinerU processing timed out after {max_wait_time} seconds")

        except ParseException:
            raise
        except Exception as e:
            self.logger.error(f"Error in MinerU processing: {e}")
            raise ParseException(f"Failed to parse PDF with MinerU: {e}")

    def _extract_text_sample(self, file_path: str, max_chars: int = 1000) -> str:
        """从PDF中提取文本样本用于语言检测

        Args:
            file_path: PDF文件路径
            max_chars: 最多提取的字符数

        Returns:
            提取的文本样本
        """
        try:
            with pdfplumber.open(file_path) as pdf:
                text = ""
                for page in pdf.pages[:3]:  # 只读取前3页
                    page_text = page.extract_text() or ""
                    text += page_text
                    if len(text) >= max_chars:
                        break
                return text[:max_chars]
        except Exception as e:
            self.logger.warning(f"Failed to extract text sample: {e}, using default language")
            return ""

    def parse(self, file_path: str) -> str:
        """Parse the PDF file and return its content as HTML string (fallback method using pdfplumber).

        使用pdfplumber的简单解析方法,作为备用方案。
        推荐使用parse_with_mineru()获得更好的解析质量。
        """
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