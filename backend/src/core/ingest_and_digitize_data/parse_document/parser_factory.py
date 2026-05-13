"""Parser factory — MinerU VLM only."""
from __future__ import annotations

from loguru import logger

from .base import ParserStrategy
from .contracts import ParseResult
from .local.parser import MinerULocalParser


class ParserFactory:
    """Factory for document parsing with MinerU VLM."""

    def __init__(self, model_server_url: str = "http://localhost:8001"):
        self._parser = MinerULocalParser(model_server_url=model_server_url)

    @property
    def parser(self) -> ParserStrategy:
        """The active parser."""
        return self._parser

    async def parse(self, pdf_path: str) -> ParseResult:
        """Parse PDF with MinerU VLM."""
        logger.info(f"Parsing with {self._parser.name}")
        return await self._parser.parse(pdf_path)
