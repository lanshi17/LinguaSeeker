"""PaddleOCR local parser implementation."""
from __future__ import annotations

import asyncio

from loguru import logger

from .base import ParserStrategy
from .contracts import (
    DocumentMetadata,
    FigurePosition,
    PageContent,
    ParseResult,
    TableStructure,
)
from .exceptions import PaddleOCRError


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

    def _run_paddle_ocr(self, pdf_path: str) -> dict:
        """Run PaddleOCR in a thread (CPU-bound)."""
        from paddleocr import PaddleOCR

        ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)

        pages = []
        full_markdown_parts = []

        result = ocr.ocr(pdf_path, cls=True)
        page_number = 1

        for page_result in result:
            lines = []
            if page_result:
                for line in page_result:
                    text = line[1][0]
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

    def _build_result(self, data: dict) -> ParseResult:
        """Convert PaddleOCR output to ParseResult."""
        metadata = DocumentMetadata(total_pages=data.get("total_pages", 1))

        pages = []
        for page_data in data.get("pages", []):
            figures = [
                FigurePosition(page=page_data["page_number"], index=f["index"], caption=f.get("caption"))
                for f in page_data.get("figures", [])
            ]
            tables = [
                TableStructure(
                    page=page_data["page_number"],
                    index=t["index"],
                    headers=t.get("headers", []),
                    rows=t.get("rows", []),
                )
                for t in page_data.get("tables", [])
            ]
            pages.append(
                PageContent(
                    page_number=page_data["page_number"],
                    markdown=page_data.get("markdown", ""),
                    figures=figures,
                    tables=tables,
                )
            )

        return ParseResult(
            metadata=metadata,
            pages=pages,
            full_markdown=data.get("full_markdown", ""),
            parser_used=self.name,
        )
