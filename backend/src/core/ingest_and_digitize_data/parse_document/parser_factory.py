"""Parser factory with automatic fallback strategy."""
from __future__ import annotations

from loguru import logger

from .base import ParserStrategy
from .contracts import ParseResult
from .exceptions import ParserExhaustedError
from .mineru_local_parser import MinerULocalParser
from .paddle_parser import PaddleOCRParser


class ParserFactory:
    """Factory that manages parser selection and automatic fallback."""

    def __init__(
        self,
        model_server_url: str = "http://localhost:8001",
        paddle_model_path: str = "",
    ):
        self._parsers: list[ParserStrategy] = [
            MinerULocalParser(model_server_url=model_server_url),
            PaddleOCRParser(model_path=paddle_model_path),
        ]

    @property
    def parsers(self) -> list[ParserStrategy]:
        """Available parsers in priority order."""
        return self._parsers

    async def parse(self, pdf_path: str) -> ParseResult:
        """Parse PDF with automatic fallback.

        Tries parsers in priority order.  Raises ParserExhaustedError
        if all parsers fail.
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

        raise ParserExhaustedError(errors=errors)
