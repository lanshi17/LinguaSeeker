"""PaddleOCR local parser implementation."""
from __future__ import annotations

import asyncio
import os
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


def _patch_paddle_inference():
    """Monkey-patch PaddleStaticRunner to work around PaddlePaddle 3.x OneDNN/PIR crash on newer Intel CPUs.

    The PaddlePaddle 3.x inference engine has a bug where the OneDNN instruction executor
    crashes with 'ConvertPirAttribute2RuntimeAttribute not support' on certain Intel CPUs.
    This patch disables the new IR and executor to use the legacy inference path.
    """
    os.environ["FLAGS_enable_new_ir"] = "0"
    os.environ["FLAGS_enable_new_executor"] = "0"

    try:
        import paddlex.inference.models.runners.paddle_static.runner as runner_mod

        _original_create = runner_mod.PaddleStaticRunner._create

        def _patched_create(self):
            import paddle
            paddle_inference = paddle.inference

            model_paths = runner_mod.get_model_paths(self.model_dir, self.model_file_prefix)
            if "paddle" not in model_paths:
                raise RuntimeError("No valid PaddlePaddle model found")

            model_file, params_file = model_paths["paddle"]
            config = paddle_inference.Config(str(model_file), str(params_file))
            config.disable_gpu()
            if hasattr(config, "disable_mkldnn"):
                config.disable_mkldnn()
            config.set_cpu_math_library_num_threads(4)
            config.set_optimization_level(0)
            if hasattr(config, "enable_new_ir"):
                config.enable_new_ir(False)

            return paddle_inference.create_predictor(config)

        runner_mod.PaddleStaticRunner._create = _patched_create
    except ImportError:
        pass


_patch_paddle_inference()


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

        ocr = PaddleOCR(use_textline_orientation=True)

        pages = []
        full_markdown_parts = []

        result = list(ocr.predict(pdf_path))
        if not result:
            raise PaddleOCRError("PaddleOCR returned empty result for the PDF")
        page_number = 1

        for page_result in result:
            lines = []
            if hasattr(page_result, "rec_texts"):
                lines = list(page_result.rec_texts)
            elif isinstance(page_result, dict) and "rec_texts" in page_result:
                lines = page_result["rec_texts"]
            elif isinstance(page_result, list):
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
