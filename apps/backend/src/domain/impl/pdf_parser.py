# 将pdf解析为html
from src.domain.abc.document_parser import DocumentParser
from loguru import logger
from src.utils.exceptions import ParseException
from typing import Any, Dict, List, Optional
from src.infrastructure.adapters.mineru import (
    MinerUAdapterInterface,
    MinerUAdapterImpl,
)
import pdfplumber
import time
import os

class PDFParser(DocumentParser):
    def __init__(self, mineru_adapter: Optional[MinerUAdapterInterface] = None):
        # Allow dependency injection but default to MinerU implementation
        self.mineru_adapter = mineru_adapter or MinerUAdapterImpl()
        logger.info("PDFParser initialized with MinerU adapter")

    def parse(self, file_path: str, document_id: Optional[str] = None, **_: Any) -> str:
        """Parse the PDF file locally and return its content as HTML string."""
        try:
            with pdfplumber.open(file_path) as pdf:
                html_content = ""
                for page in pdf.pages:
                    html_content += page.to_html()
            logger.info(f"Successfully parsed PDF file: {file_path}")
            return html_content
        except Exception as e:
            logger.error(f"Error parsing PDF file {file_path}: {e}")
            raise ParseException(f"Failed to parse PDF file: {e}")

    def parse_with_mineru(
        self,
        file_path: str,
        document_id: Optional[str] = None,
        *,
        language_hint: Optional[List[str]] = None,
        poll_interval: float = 2.0,
        timeout_seconds: float = 300.0,
    ) -> Dict[str, Any]:
        """Submit the PDF to MinerU for processing and return metadata about the result."""
        if not os.path.exists(file_path):
            raise ParseException(f"PDF file does not exist: {file_path}")

        try:
            if language_hint:
                logger.info(
                    "Language hints provided (%s) but MinerU requests no longer send explicit language configuration",
                    language_hint,
                )

            logger.info("Submitting %s to MinerU", file_path)
            upload_response = self.mineru_adapter.apply_upload_urls([file_path])
            file_entries = upload_response.get("files") or []
            if not file_entries:
                raise ParseException("MinerU did not return upload information for the file")

            file_entry = file_entries[0]
            file_id = file_entry.get("file_id")
            upload_url = file_entry.get("upload_url")
            if not file_id or not upload_url:
                raise ParseException("MinerU upload information is missing file_id or upload_url")

            self.mineru_adapter.upload_to_urls([file_path], [upload_url])
            status = self._wait_for_completion(file_id, poll_interval, timeout_seconds)
            extract_result = status.get("extract_result") or {}
            state = extract_result.get("state")
            if state != "done":
                error_message = extract_result.get("err_msg") or f"MinerU processing failed with state={state}"
                raise ParseException(error_message)

            result_payload = self.mineru_adapter.retrieve_results(file_id)
            extract_result = result_payload.get("extract_result") or {}
            full_zip_url = extract_result.get("full_zip_url")
            if not full_zip_url:
                raise ParseException("MinerU did not provide a ZIP download URL")

            return {
                "document_id": document_id,
                "file_id": extract_result.get("file_id") or file_id,
                "file_name": extract_result.get("file_name") or os.path.basename(file_path),
                "state": extract_result.get("state") or state,
                "full_zip_url": full_zip_url,
            }
        except ParseException:
            raise
        except Exception as exc:  # pragma: no cover - defensive guard around adapter failures
            logger.error(f"Unexpected MinerU parsing error for {file_path}: {exc}")
            raise ParseException(str(exc)) from exc

    def validate(self, content: str) -> bool:
        """Validate the parsed HTML content."""
        if "<html>" in content and "</html>" in content:
            logger.info("Parsed content is valid HTML")
            return True
        else:
            logger.warning("Parsed content is not valid HTML")
            return False

    def save(self, content: str, destination: str) -> None:
        """Save the HTML content to the specified destination."""
        try:
            with open(destination, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"Successfully saved HTML content to: {destination}")
        except Exception as e:
            logger.error(f"Error saving HTML content to {destination}: {e}")
            raise ParseException(f"Failed to save HTML content: {e}")

    def _wait_for_completion(
        self,
        file_id: str,
        poll_interval: float,
        timeout_seconds: float,
    ) -> Dict[str, Any]:
        start = time.monotonic()
        while True:
            status = self.mineru_adapter.get_processing_status(file_id)
            extract_result = status.get("extract_result") or {}
            state = extract_result.get("state")
            if state in {"done" ,"failed"}:
                return status
            if time.monotonic() - start > timeout_seconds:
                raise ParseException(f"MinerU processing timed out for file {file_id}")
            logger.info(
                "MinerU still processing file %s (state=%s), waiting %.1fs",
                file_id,
                state,
                poll_interval,
            )
            time.sleep(poll_interval)
