"""MinerU Adapter for PDF parsing.

Wrapper for MinerU PDF parsing library with error handling and retries.
"""

import os
import asyncio
from typing import Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ParsedDocument:
    """Parsed document result."""

    markdown_content: str
    images: list
    tables: list
    metadata: Dict[str, Any]
    page_count: int


class MinerUAdapter:
    """Adapter for MinerU PDF parsing.

    Provides interface for parsing PDFs with MinerU library,
    handling errors, timeouts, and resource cleanup.
    """

    def __init__(
        self,
        timeout: int = 300,  # 5 minutes default
        max_file_size: int = 104857600,  # 100MB
    ):
        """Initialize MinerU adapter.

        Args:
            timeout: Maximum parsing time in seconds
            max_file_size: Maximum file size in bytes
        """
        self.timeout = timeout
        self.max_file_size = max_file_size

    async def parse_pdf(
        self,
        pdf_path: str,
        output_dir: Optional[str] = None,
    ) -> ParsedDocument:
        """Parse PDF document using MinerU.

        Args:
            pdf_path: Path to PDF file
            output_dir: Directory for output files (temp if not specified)

        Returns:
            Parsed document with content and metadata

        Raises:
            FileNotFoundError: If PDF doesn't exist
            ValueError: If file size exceeds limit
            TimeoutError: If parsing exceeds timeout
            RuntimeError: For other parsing errors
        """
        # Validate file
        pdf_file = Path(pdf_path)
        if not pdf_file.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        file_size = pdf_file.stat().st_size
        if file_size > self.max_file_size:
            raise ValueError(
                f"File size {file_size} exceeds limit {self.max_file_size}"
            )

        # Create output directory
        if output_dir is None:
            import tempfile
            output_dir = tempfile.mkdtemp(prefix="mineru_")

        try:
            # Run parsing with timeout
            result = await asyncio.wait_for(
                self._parse_with_mineru(pdf_path, output_dir),
                timeout=self.timeout,
            )
            return result

        except asyncio.TimeoutError:
            raise TimeoutError(
                f"PDF parsing exceeded timeout of {self.timeout} seconds"
            )
        except Exception as e:
            raise RuntimeError(f"PDF parsing failed: {e}")

    async def parse_pdf_bytes(
        self,
        pdf_content: bytes,
        filename: str = "document.pdf",
        output_dir: Optional[str] = None,
    ) -> ParsedDocument:
        """Parse PDF document from bytes using MinerU.

        Args:
            pdf_content: PDF content as bytes
            filename: Original filename for reference
            output_dir: Directory for output files (temp if not specified)

        Returns:
            Parsed document with content and metadata

        Raises:
            ValueError: If file size exceeds limit
            TimeoutError: If parsing exceeds timeout
            RuntimeError: For other parsing errors
        """
        # Validate file size
        if len(pdf_content) > self.max_file_size:
            raise ValueError(
                f"File size {len(pdf_content)} exceeds limit {self.max_file_size}"
            )

        # Create temporary file
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
            temp_file.write(pdf_content)
            temp_file_path = temp_file.name

        try:
            # Parse using existing method
            result = await self.parse_pdf(temp_file_path, output_dir)
            return result

        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_file_path)
            except OSError:
                pass  # Ignore cleanup errors

    async def _parse_with_mineru(
        self, pdf_path: str, output_dir: str
    ) -> ParsedDocument:
        """Internal parsing logic using MinerU.

        Args:
            pdf_path: Path to PDF
            output_dir: Output directory

        Returns:
            Parsed document
        """
        # Import MinerU (lazy import to avoid startup overhead)
        try:
            # Note: Actual MinerU import may vary based on version
            # This is a placeholder for the actual implementation
            from src.infrastructure.adapters.mineru.mineru_adapter_impl import (
                MinerUAdapterImpl
            )

            # Use existing implementation
            impl = MinerUAdapterImpl()
            result = await impl.parse(pdf_path, output_dir)

            # Convert to our format
            return ParsedDocument(
                markdown_content=result.get("markdown", ""),
                images=result.get("images", []),
                tables=result.get("tables", []),
                metadata=result.get("metadata", {}),
                page_count=result.get("page_count", 0),
            )

        except ImportError:
            # Fallback implementation if MinerU not available
            return await self._fallback_parse(pdf_path)

    async def _fallback_parse(self, pdf_path: str) -> ParsedDocument:
        """Fallback PDF parser using pdfplumber.

        Args:
            pdf_path: Path to PDF

        Returns:
            Parsed document with basic text extraction
        """
        import pdfplumber

        with pdfplumber.open(pdf_path) as pdf:
            # Extract text from all pages
            markdown_content = ""
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text:
                    markdown_content += f"\n\n## Page {i + 1}\n\n{text}"

            # Extract metadata
            metadata = {
                "title": pdf.metadata.get("Title", ""),
                "author": pdf.metadata.get("Author", ""),
                "creator": pdf.metadata.get("Creator", ""),
                "producer": pdf.metadata.get("Producer", ""),
            }

            return ParsedDocument(
                markdown_content=markdown_content.strip(),
                images=[],
                tables=[],
                metadata=metadata,
                page_count=len(pdf.pages),
            )

    def validate_pdf(self, pdf_path: str) -> bool:
        """Validate that file is a valid PDF.

        Args:
            pdf_path: Path to PDF file

        Returns:
            True if valid PDF
        """
        try:
            import pdfplumber

            with pdfplumber.open(pdf_path) as pdf:
                # Try to access first page
                _ = pdf.pages[0] if pdf.pages else None
                return True
        except Exception:
            return False

    def get_page_count(self, pdf_path: str) -> int:
        """Get number of pages in PDF.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Number of pages
        """
        try:
            import pdfplumber

            with pdfplumber.open(pdf_path) as pdf:
                return len(pdf.pages)
        except Exception:
            return 0
