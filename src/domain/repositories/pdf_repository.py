"""PDF repository interface."""

from abc import ABC, abstractmethod

from ..value_objects import Language


class PDFRepository(ABC):
    """Abstract repository for PDF operations."""

    @abstractmethod
    def extract_text(self, pdf_path: str) -> str:
        """Extract text from PDF.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Extracted text content
        """

    @abstractmethod
    def extract_text_with_bbox(self, pdf_path: str) -> tuple[str, list[dict]]:
        """Extract text plus Text-with-Bbox metadata.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Tuple of (markdown text, bbox metadata list). Bbox metadata should include
            page index, bounding box coordinates, and raw text for each fragment.
        """

    @abstractmethod
    def detect_language(self, pdf_path: str) -> Language:
        """Detect language from PDF.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Detected language
        """

    @abstractmethod
    def ocr_to_markdown(self, pdf_path: str, lang: Language) -> str:
        """Convert PDF pages to markdown via OCR.

        Args:
            pdf_path: Path to PDF file
            lang: Language hint for OCR

        Returns:
            Markdown formatted text
        """

    @abstractmethod
    def get_page_count(self, pdf_path: str) -> int:
        """Get total page count of a PDF."""

    @abstractmethod
    def is_scanned_pdf(self, pdf_path: str) -> bool:
        """Determine if PDF is scanned (image-based) or native searchable.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            True if scanned/image-based, False if native text-based
        """

    @abstractmethod
    def extract_figures_and_tables(
        self, pdf_path: str, bbox_metadata: list[dict]
    ) -> tuple[list[dict], list[dict]]:
        """Detect and extract figures and tables from PDF.
        
        P2 Feature: Figure and Table Detection
        
        Args:
            pdf_path: Path to PDF file
            bbox_metadata: Bounding box metadata from OCR
            
        Returns:
            Tuple of (figures, tables) where each contains:
            - type: "figure" or "table"
            - title: Figure/table title
            - caption: Extracted caption text
            - page: Page number
            - bbox: Bounding box coordinates
            - image_path: (optional) Path to extracted screenshot
        """

        @abstractmethod
        def extract_html(self, pdf_path: str, out_dir: str, enable_translation: bool = True, detected_language: str = None) -> dict:
                """Extract structured HTML using MinerU if available.
                
                Args:
                    pdf_path: Path to PDF file
                    out_dir: Output directory
                    enable_translation: Whether to generate English translation
                    detected_language: Pre-detected language code (e.g., 'ch', 'en', 'ja').
                                      If provided, MinerU will use this language.

                Returns a dict with keys:
                    - original_structured_html
                    - translated_english_html
                    - bbox_metadata_json
                    - detected_language
                    - figures_dir
                """
