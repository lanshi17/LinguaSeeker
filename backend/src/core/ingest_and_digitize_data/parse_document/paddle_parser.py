"""PaddleOCR local parser implementation."""
from __future__ import annotations

import asyncio
from typing import TypedDict

from loguru import logger

from .base import ParserStrategy
from .contracts import (
    DocumentMetadata,
    ParseResult,
    pages_from_raw,
)
from .exceptions import PaddleOCRError


class _PaddleOCRPageData(TypedDict):
    page_number: int
    markdown: str
    figures: list[dict]
    tables: list[dict]


class _PaddleOCRRawResult(TypedDict):
    total_pages: int
    pages: list[_PaddleOCRPageData]
    full_markdown: str


class PaddleOCRParser(ParserStrategy):
    """PDF parser using locally deployed PaddleOCR-VL-1.5."""

    def __init__(self, model_path: str):
        self._model_path = model_path

    @property
    def name(self) -> str:
        return "paddleocr"

    async def parse(self, pdf_path: str) -> ParseResult:
        """Parse PDF via local PaddleOCR."""
        logger.info(f"PaddleOCR parsing: {pdf_path}")

        try:
            result = await asyncio.to_thread(self._run_paddle_ocr, pdf_path)
        except Exception as e:
            raise PaddleOCRError(f"PaddleOCR failed: {e}") from e

        return self._build_result(result)

    def _run_paddle_ocr(self, pdf_path: str) -> _PaddleOCRRawResult:
        """Run PaddleOCR in a thread (CPU-bound)."""
        try:
            from paddleocr import PaddleOCR
        except ImportError:
            raise PaddleOCRError("PaddleOCR is not installed. Install with: uv add paddleocr")

        ocr = PaddleOCR(use_angle_cls=True, show_log=False)

        pages = []
        full_markdown_parts = []

        result = list(ocr.predict(pdf_path))
        if not result:
            raise PaddleOCRError("PaddleOCR returned empty result for the PDF")
        page_number = 1

        for page_result in result:
            lines = []
            if hasattr(page_result, "rec_texts"):
                # New PaddleOCR v3+ API
                lines = list(page_result.rec_texts)
            elif isinstance(page_result, dict) and "rec_texts" in page_result:
                lines = page_result["rec_texts"]
            elif isinstance(page_result, list):
                # Legacy API fallback
                for line in page_result:
                    if isinstance(line, (list, tuple)) and len(line) >= 2:
                        text = line[1][0] if isinstance(line[1], (list, tuple)) else str(line[1])
                        lines.append(text)

            markdown = "\n".join(lines)
            full_markdown_parts.append(markdown)

            pages.append(
                {
                    "page_number": page_number,
                    "markdown": markdown,
                    "figures": [],
                    "tables": [],
                }
            )
            page_number += 1

        return {
            "total_pages": len(pages),
            "pages": pages,
            "full_markdown": "\n\n".join(full_markdown_parts),
        }

    def _build_result(self, data: _PaddleOCRRawResult) -> ParseResult:
        """Convert PaddleOCR output to ParseResult."""
        metadata = DocumentMetadata(total_pages=data.get("total_pages", 1))

        return ParseResult(
            metadata=metadata,
            pages=pages_from_raw(data.get("pages", [])),
            full_markdown=data.get("full_markdown", ""),
            parser_used=self.name,
        )
