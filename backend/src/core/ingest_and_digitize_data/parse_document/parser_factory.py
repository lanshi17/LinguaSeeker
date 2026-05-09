"""Parser factory with automatic fallback strategy."""
from __future__ import annotations

from loguru import logger

from .base import ParserStrategy
from .contracts import ParseResult
from .exceptions import ParserExhaustedError
from .mineru_parser import MinerUParser
from .paddle_parser import PaddleOCRParser


class ParserFactory:
    """Factory that manages parser selection and automatic fallback."""

    def __init__(
        self,
        mineru_api_token: str,
        paddle_model_path: str = "",
    ):
        self._mineru_parser = MinerUParser(api_token=mineru_api_token)
        self._paddle_parser = PaddleOCRParser(model_path=paddle_model_path)

    @property
    def parsers(self) -> list[ParserStrategy]:
        """Available parsers in priority order."""
        return [self._mineru_parser, self._paddle_parser]

    async def parse(self, pdf_path: str) -> ParseResult:
        """Parse PDF with automatic fallback.

        Tries MinerU first, falls back to PaddleOCR on failure.
        Raises ParserExhaustedError if all parsers fail.
        """
        errors: dict[str, Exception] = {}

        for parser in self.parsers:
            try:
                logger.info(f"Attempting parse with {parser.name}")
                result = await parser.parse(pdf_path)
                logger.info(f"Parse succeeded with {parser.name}")
                return result
            except Exception as e:
                logger.warning(f"Parser {parser.name} failed: {e}")
                errors[parser.name] = e
                continue

        raise ParserExhaustedError(
            mineru_error=errors.get("mineru"),
            paddle_error=errors.get("paddleocr"),
        )
