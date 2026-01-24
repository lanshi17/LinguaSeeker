"""Language detection domain service."""

from abc import ABC, abstractmethod

from ..repositories import PDFRepository
from ..value_objects import Language


class LanguageDetectorService(ABC):
    """Domain service for language detection."""

    @abstractmethod
    def detect(self, pdf_path: str) -> Language:
        """Detect language from PDF.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Detected language
        """
