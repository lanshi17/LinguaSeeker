"""PDF repository implementation."""

from collections import Counter
from typing import Optional

import pytesseract
from langchain_community.document_loaders import PyPDFLoader
from langdetect import detect
from pdf2image import convert_from_path, pdfinfo_from_path

# Using absolute imports from src root
from src.domain.repositories import PDFRepository
from src.domain.value_objects import Language
from src.infrastructure.utils.exceptions import LanguageDetectionError, ParsingException
from src.infrastructure.ocr import QwenOCRService
from src.infrastructure.utils.config import LLMConfig


class PDFRepositoryImpl(PDFRepository):
    """Concrete implementation of PDF repository."""

    def __init__(self, ocr_config: Optional[LLMConfig] = None):
        """Initialize PDF repository.
        
        Args:
            ocr_config: LLM configuration for OCR service. If None, will use fallback tesseract.
        """
        self.ocr_service = QwenOCRService(
            ocr_config, 
            batch_size=ocr_config.ocr_batch_size
        ) if ocr_config else None

    def extract_text(self, pdf_path: str) -> str:
        try:
            loader = PyPDFLoader(pdf_path)
            docs = loader.load()
            return "\n".join(doc.page_content for doc in docs)
        except Exception as exc:  # noqa: BLE001
            raise ParsingException(str(exc))

    def extract_text_with_bbox(self, pdf_path: str) -> tuple[str, list[dict]]:
        """OCR to markdown while capturing bbox metadata per fragment.

        Returns markdown text and a list of fragments:
        {"page": int, "bbox": [x1, y1, x2, y2], "text": str, "fragment_id": int}
        """
        images = convert_from_path(pdf_path)
        md_pages = []
        fragments = []
        fragment_id = 0

        lang_hint = "eng"
        try:
            lang_hint = self._map_lang_to_ocr_code(self.detect_language(pdf_path))
        except Exception:
            lang_hint = "eng"

        for idx, page in enumerate(images, 1):

            data = pytesseract.image_to_data(page, lang=lang_hint, output_type=pytesseract.Output.DICT)
            page_lines = []
            for i in range(len(data["text"])):
                text = data["text"][i].strip()
                if not text:
                    continue
                
                # Fix encoding issues - especially for CJK text from OCR
                text = self._fix_ocr_encoding(text)
                
                x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
                fragment = {
                    "page": idx,
                    "bbox": [x, y, x + w, y + h],
                    "text": text,
                    "fragment_id": fragment_id,
                }
                fragments.append(fragment)
                page_lines.append(text)
                fragment_id += 1

            page_md = f"# Page {idx}\n\n" + " ".join(page_lines)
            md_pages.append(page_md)

        return "\n\n---\n\n".join(md_pages), fragments

    @staticmethod
    def _fix_ocr_encoding(text: str) -> str:
        """Fix encoding issues in OCR output, especially for CJK text.
        
        Handles mojibake where CP932/Shift_JIS bytes were misinterpreted as UTF-8.
        
        Args:
            text: Potentially garbled text from OCR
            
        Returns:
            Properly encoded UTF-8 text
        """
        if not text:
            return text
        
        # Check if text is bytes (shouldn't happen but handle it)
        if isinstance(text, bytes):
            try:
                return text.decode('utf-8', errors='replace')
            except:
                try:
                    return text.decode('cp932', errors='replace')
                except:
                    return str(text)
        
        # Check if text appears to be mojibake (CP932 bytes misinterpreted as Latin-1/UTF-8)
        # Mojibake typically has many high-byte characters in the 0x80-0xFF range
        has_high_bytes = any(0x80 <= ord(c) <= 0xFF for c in text)
        has_cjk = any('\u4e00' <= c <= '\u9fff' or '\u3040' <= c <= '\u309f' or '\u30a0' <= c <= '\u30ff' for c in text)
        
        if has_high_bytes and not has_cjk:
            # Likely mojibake - try to fix it
            try:
                # Convert to bytes using Latin-1 (which preserves the byte values)
                # then decode as CP932 (Shift_JIS for Japanese)
                fixed_text = text.encode('latin-1').decode('cp932', errors='replace')
                # Verify it looks better now (has some CJK characters)
                if any('\u4e00' <= c <= '\u9fff' or '\u3040' <= c <= '\u309f' or '\u30a0' <= c <= '\u30ff' for c in fixed_text):
                    return fixed_text
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
        
        return text

    def extract_html_with_bbox(self, pdf_path: str) -> tuple[str, list[dict]]:
        """Extract HTML using OCR-LLM while capturing bbox metadata.

        Uses Qwen-VL-OCR to extract HTML formatted content and pytesseract for bbox.
        
        Returns:
            Tuple of (HTML content, bbox metadata list)
        """
        # Use OCR-LLM to get HTML content
        if self.ocr_service:
            html_content = self.ocr_service.pdf_to_html(pdf_path)
        else:
            # Fallback to basic text extraction if no OCR service
            text = self.extract_text(pdf_path)
            # Wrap in basic HTML tags
            html_content = f"<div>{text.replace(chr(10), '<br />')}</div>"
        
        # Get bbox metadata using pytesseract
        images = convert_from_path(pdf_path)
        fragments = []
        fragment_id = 0

        lang_hint = "eng"
        try:
            lang_hint = self._map_lang_to_ocr_code(self.detect_language(pdf_path))
        except Exception:
            lang_hint = "eng"

        for idx, page in enumerate(images, 1):
            data = pytesseract.image_to_data(page, lang=lang_hint, output_type=pytesseract.Output.DICT)
            for i in range(len(data["text"])):
                text = data["text"][i].strip()
                if not text:
                    continue
                
                # Fix encoding issues
                text = self._fix_ocr_encoding(text)
                
                x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
                fragment = {
                    "page": idx,
                    "bbox": [x, y, x + w, y + h],
                    "text": text,
                    "fragment_id": fragment_id,
                }
                fragments.append(fragment)
                fragment_id += 1

        return html_content, fragments

    def detect_language(self, pdf_path: str) -> Language:
        text = self.extract_text(pdf_path)
        if not text.strip():
            images = convert_from_path(pdf_path, first_page=1, last_page=1)
            ocr_text = pytesseract.image_to_string(images[0])
            text = ocr_text or ""

        if not text.strip():
            raise LanguageDetectionError("Could not extract text for detection")

        # Heuristic detection based on character blocks
        heuristics = self._heuristic_language_scores(text)
        best_lang, best_score = max(heuristics.items(), key=lambda kv: kv[1])

        # If heuristic confidence is low, fall back to langdetect
        if best_score < 0.25:
            try:
                detected_code = detect(text)
                return Language.from_detected_code(detected_code)
            except Exception as exc:  # noqa: BLE001
                raise LanguageDetectionError(str(exc))

        return Language.from_detected_code(best_lang)

    def ocr_to_markdown(self, pdf_path: str, lang: Language) -> str:
        """Convert PDF to markdown using OCR.
        
        Args:
            pdf_path: Path to PDF file
            lang: Detected language (may be ignored if using Qwen OCR)
            
        Returns:
            Markdown formatted text
        """
        # Use Qwen OCR if available
        if self.ocr_service:
            try:
                return self.ocr_service.pdf_to_markdown(pdf_path)
            except Exception as e:
                # Fallback to tesseract if Qwen OCR fails
                import traceback
                print(f"Qwen OCR failed, falling back to tesseract: {e}")
                traceback.print_exc()
        
        # Fallback: Use tesseract OCR
        images = convert_from_path(pdf_path)
        md_pages = []
        for i, page in enumerate(images, 1):
            # Map Language enum to tesseract language code
            lang_code = self._map_lang_to_ocr_code(lang)
            text = pytesseract.image_to_string(page, lang=lang_code)
            md_pages.append(f"# Page {i}\n\n{text}")
        return "\n\n---\n\n".join(md_pages)

    def get_page_count(self, pdf_path: str) -> int:
        try:
            info = pdfinfo_from_path(pdf_path)
            return int(info.get("Pages", 0))
        except Exception:
            # Fallback: load via PyPDFLoader
            try:
                loader = PyPDFLoader(pdf_path)
                return len(loader.load())
            except Exception:
                return 0

    def is_scanned_pdf(self, pdf_path: str) -> bool:
        """Determine if PDF is scanned based on text extraction quality.
        
        Returns True if any page has <50 chars or low confidence.
        """
        try:
            loader = PyPDFLoader(pdf_path)
            docs = loader.load()
            for doc in docs[:min(3, len(docs))]:  # Check first 3 pages
                text = doc.page_content.strip()
                if len(text) < 50:
                    return True
            return False
        except Exception:
            # If extraction fails, assume scanned
            return True

    @staticmethod
    def _map_lang_to_ocr_code(lang: Language) -> str:
        mapping = {
            Language.CHINESE: "chi_sim",
            Language.JAPANESE: "jpn",
            Language.ENGLISH: "eng",
            Language.RUSSIAN: "rus",
            Language.GERMAN: "deu",
            Language.FRENCH: "fra",
        }
        return mapping.get(lang, "eng")

    @staticmethod
    def _heuristic_language_scores(text: str) -> dict:
        """Heuristic script-based language scoring without API calls."""
        scores = {"zh": 0.0, "ja": 0.0, "en": 0.0, "ru": 0.0, "de": 0.0, "fr": 0.0}
        counters = Counter()
        for ch in text[:5000]:
            code = ord(ch)
            if 0x4e00 <= code <= 0x9fff:
                counters["zh"] += 1
            elif 0x3040 <= code <= 0x30ff:
                counters["ja"] += 1
            elif 0x0400 <= code <= 0x04FF:
                counters["ru"] += 1
            elif ch.isalpha():
                counters["latin"] += 1

        total = sum(counters.values()) or 1
        scores["zh"] = counters["zh"] / total
        scores["ja"] = counters["ja"] / total
        scores["ru"] = counters["ru"] / total
        latin_ratio = counters["latin"] / total
        # Split latin between en/de/fr using naive heuristics
        scores["en"] = latin_ratio * 0.5
        scores["de"] = latin_ratio * 0.25
        scores["fr"] = latin_ratio * 0.25
        return scores

    def extract_figures_and_tables(
        self, pdf_path: str, bbox_metadata: list[dict]
    ) -> tuple[list[dict], list[dict]]:
        """P2 Feature: Detect and extract figures and tables from PDF.
        
        Args:
            pdf_path: Path to PDF file
            bbox_metadata: Bounding box metadata from OCR
            
        Returns:
            Tuple of (figures, tables) with metadata and optional images
        """
        from src.domain.services.figure_table_detector import FigureTableDetector
        
        # Step 1: Detect figure/table locations using keyword patterns
        figures, tables = FigureTableDetector.detect_figure_table_locations(
            bbox_metadata
        )
        
        # Step 2: Extract complete regions with captions
        enhanced_figures, enhanced_tables = (
            FigureTableDetector.extract_figure_table_regions(
                bbox_metadata, figures, tables
            )
        )
        
        # Step 3: Extract PDF page images and create figure/table screenshots
        try:
            images = convert_from_path(pdf_path)
            
            # Add image paths for figures and tables
            for fig in enhanced_figures:
                page_idx = fig["page"] - 1
                if 0 <= page_idx < len(images):
                    # Store page image reference (actual screenshot extraction
                    # can be done on demand based on bbox)
                    fig["page_image_available"] = True
                    fig["image_path"] = None  # Lazy loading
                    
            for tbl in enhanced_tables:
                page_idx = tbl["page"] - 1
                if 0 <= page_idx < len(images):
                    tbl["page_image_available"] = True
                    tbl["image_path"] = None  # Lazy loading
                    
        except Exception:
            # If PDF image conversion fails, still return detected metadata
            pass
        
        return enhanced_figures, enhanced_tables
