"""Document parse orchestrator with remote-first fallback."""
from __future__ import annotations

from loguru import logger

from .base import ParserStrategy
from .contracts import ParseResult
from .exceptions import ParserExhaustedError


class DocumentParseOrchestrator(ParserStrategy):
    """Orchestrator that tries remote parser first, then falls back to local.

    Implements ParserStrategy interface for seamless integration.
    """

    def __init__(self, remote: ParserStrategy, local: ParserStrategy):
        self._remote = remote
        self._local = local

    @property
    def name(self) -> str:
        return "orchestrator"

    async def parse(self, pdf_path: str) -> ParseResult:
        """Parse PDF with remote-first fallback strategy.

        Args:
            pdf_path: URL to the PDF file.

        Returns:
            ParseResult from successful parser.

        Raises:
            ParserExhaustedError: If both remote and local parsers fail.
        """
        errors: dict[str, Exception] = {}

        # Try remote first
        try:
            logger.info(f"Attempting remote parsing: {pdf_path}")
            result = await self._remote.parse(pdf_path)
            logger.info(f"Remote parsing succeeded: {pdf_path}")
            return result
        except Exception as e:
            logger.warning(f"Remote parsing failed: {e}")
            errors[self._remote.name] = e

        # Fallback to local
        try:
            logger.info(f"Attempting local parsing: {pdf_path}")
            result = await self._local.parse(pdf_path)
            logger.info(f"Local parsing succeeded: {pdf_path}")
            return result
        except Exception as e:
            logger.warning(f"Local parsing failed: {e}")
            errors[self._local.name] = e

        # Both failed
        raise ParserExhaustedError(errors=errors)
