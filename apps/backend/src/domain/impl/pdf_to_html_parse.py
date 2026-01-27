# 将pdf解析为html 
from domain.abc.document_parser import DocumentParser
from utils.logger import Logger
from utils.exceptions import ParseException
from typing import Any
from infrastructure.adapters.mineru import MinerUInterface
from utils.file_utils import download_file, extract_zip, find_file_in_directory, create_temp_directory
import os
import time

class PDFToHTMLParser(DocumentParser):
    # Default configuration for MinerU processing
    DEFAULT_MAX_WAIT_TIME = 300  # 5 minutes
    DEFAULT_POLL_INTERVAL = 10   # 10 seconds
    
    def __init__(self, mineru_adapter: MinerUInterface, max_wait_time: int = DEFAULT_MAX_WAIT_TIME, 
                 poll_interval: int = DEFAULT_POLL_INTERVAL):
        self.mineru_adapter = mineru_adapter
        self.max_wait_time = max_wait_time
        self.poll_interval = poll_interval
        self.logger = Logger.get_logger("PDFToHTMLParser")
        self.logger.info("PDFToHTMLParser initialized with MinerU adapter")
        
    def parse(self, file_path: str) -> str:
        """Parse the PDF file and return its content as HTML string.
        
        Uses MinerU adapter to process the file through a pipeline that:
        1. Uploads the file to MinerU service
        2. Processes it to extract content
        3. Downloads the result as a zip file
        4. Extracts the zip to get HTML and other resources
        5. Returns the formatted HTML content
        """
        temp_dir = None
        try:
            # TODO: 调用mineru适配器处理文件流水线,会返回一个zip的下载链接,
            # 下载解压后里面包含解析后的json和html文件和图片等资源,传给pdf_parser进行格式化处理
            
            self.logger.info(f"Starting MinerU pipeline processing for: {file_path}")
            
            # Step 1: Call mineru adapter pipeline process
            processing_results = self.mineru_adapter.pipline_process([file_path])
            
            if not processing_results:
                raise ParseException("MinerU pipeline processing returned no results")
            
            # Step 2: Get the first file result
            file_id = list(processing_results.keys())[0]
            result = processing_results[file_id]
            
            # Step 3: Wait for processing to complete if needed
            extract_result = result.get("extract_result", {})
            state = extract_result.get("state")
            
            # Poll for completion if still running
            elapsed_time = 0
            
            while state == "running" and elapsed_time < self.max_wait_time:
                self.logger.info(f"Processing still running, waiting {self.poll_interval}s...")
                time.sleep(self.poll_interval)
                elapsed_time += self.poll_interval
                
                # Check status again
                status = self.mineru_adapter.get_processing_status(file_id)
                extract_result = status.get("extract_result", {})
                state = extract_result.get("state")
                
                if state == "completed":
                    result = self.mineru_adapter.retrieve_results(file_id)
                    extract_result = result.get("extract_result", {})
                    break
            
            if state != "completed":
                raise ParseException(f"MinerU processing failed or timed out. State: {state}")
            
            # Step 4: Get the zip download URL
            zip_url = extract_result.get("full_zip_url")
            if not zip_url:
                raise ParseException("No zip download URL in MinerU results")
            
            self.logger.info(f"Got zip download URL: {zip_url}")
            
            # Step 5: Download the zip file
            temp_dir = create_temp_directory("mineru_extract_")
            zip_path = os.path.join(temp_dir, "result.zip")
            download_file(zip_url, zip_path)
            
            # Step 6: Extract the zip file
            extract_dir = os.path.join(temp_dir, "extracted")
            extract_zip(zip_path, extract_dir)
            
            # Step 7: Find and read the HTML file
            html_file_path = find_file_in_directory(extract_dir, ".html")
            
            with open(html_file_path, "r", encoding="utf-8") as f:
                html_content = f.read()
            
            self.logger.info(f"Successfully parsed PDF file: {file_path}")
            return html_content
            
        except Exception as e:
            self.logger.error(f"Error parsing PDF file {file_path}: {e}")
            raise ParseException(f"Failed to parse PDF file: {e}")
        finally:
            # Cleanup temporary directory
            if temp_dir and os.path.exists(temp_dir):
                import shutil
                try:
                    shutil.rmtree(temp_dir)
                    self.logger.info(f"Cleaned up temporary directory: {temp_dir}")
                except Exception as e:
                    self.logger.warning(f"Failed to cleanup temporary directory {temp_dir}: {e}")

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