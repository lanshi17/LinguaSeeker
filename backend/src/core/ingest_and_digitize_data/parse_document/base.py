"""Abstract base class for document parsers."""
from __future__ import annotations

from abc import ABC, abstractmethod

from .contracts import ParseResult


class ParserStrategy(ABC):
    """Abstract base for PDF parser implementations."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Parser identifier for logging and result tracking."""

    @abstractmethod
    async def parse(self, pdf_path: str) -> ParseResult:
        """Parse a PDF file and return structured results.

        Args:
            pdf_path: Path to the PDF file (local path or URL).

        Returns:
            ParseResult with metadata, pages, and full markdown.

        Raises:
            ParseDocumentError: On parsing failure.
        """
