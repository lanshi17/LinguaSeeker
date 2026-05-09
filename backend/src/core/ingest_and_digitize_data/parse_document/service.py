"""Public service interface for document parsing."""
from __future__ import annotations

import json
from pathlib import Path

import rust_io.files as files_io
from loguru import logger

from .contracts import ParseResult
from .parser_factory import ParserFactory


class ParseDocumentService:
    """High-level service for PDF parsing with file I/O delegation."""

    def __init__(
        self,
        mineru_api_token: str,
        paddle_model_path: str = "",
    ):
        self._factory = ParserFactory(
            mineru_api_token=mineru_api_token,
            paddle_model_path=paddle_model_path,
        )

    async def parse(self, pdf_url: str) -> ParseResult:
        """Parse a PDF file and return structured results.

        Args:
            pdf_url: URL to the PDF file (S3/MinIO or public URL).

        Returns:
            ParseResult with metadata, pages, and full markdown.
        """
        return await self._factory.parse(pdf_url)

    async def parse_and_save(
        self,
        pdf_url: str,
        output_dir: str,
    ) -> ParseResult:
        """Parse PDF and save markdown output to files.

        Args:
            pdf_url: URL to the PDF file.
            output_dir: Directory to save output files.

        Returns:
            ParseResult from the parser.
        """
        result = await self._factory.parse(pdf_url)

        md_path = str(Path(output_dir) / "output.md")
        files_io.File(md_path).write(result.full_markdown)
        logger.info(f"Saved markdown to {md_path}")

        meta_path = str(Path(output_dir) / "metadata.json")
        files_io.File(meta_path).write(json.dumps(result.metadata.model_dump(), indent=2))
        logger.info(f"Saved metadata to {meta_path}")

        return result

    async def check_duplicate(
        self,
        file_path: str,
        known_hashes: list[str],
    ) -> dict:  # noqa: dict-return
        """Check if a file is a duplicate based on content hash.

        Args:
            file_path: Path to the file to check.
            known_hashes: List of known content hashes.

        Returns:
            Dict with 'hash' and 'is_duplicate' keys.
        """
        return files_io.check_duplicate(file_path, known_hashes)
