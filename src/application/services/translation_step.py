"""Translation step - handles document translation to English with glossary support."""

from pathlib import Path
from typing import List, Optional
import re
from collections import Counter

from src.domain.interfaces.pipeline_step import IPipelineStep, IPipelineContext
from src.domain.services import TranslatorService
from src.infrastructure.utils.logger import Logger


class TranslationStep(IPipelineStep):
    """Pipeline step responsible for translating content to English.
    
    Responsibilities:
    - Split long documents for translation management
    - Maintain terminology consistency via glossary
    - Handle translation timeouts and retries
    
    Input context keys:
    - raw_html: HTML to translate
    - detected_language: Source language
    - page_count: Number of pages (for optimization)
    - out_dir: Output directory
    - pdf_path: Original PDF path (for naming)
    
    Output context keys:
    - english_html: Translated English HTML content
    - english_html_path: Path to saved English HTML file
    - glossary_terms: Extracted key terminology
    """

    def __init__(self, translator: TranslatorService):
        """Initialize translation step.
        
        Args:
            translator: Translation service
        """
        self.translator = translator
        self.logger = Logger.get_logger(__name__)
        # Align with translator batch size
        self.max_chunk_size = 8000  # characters per chunk

    @property
    def name(self) -> str:
        """Get step name."""
        return "translation"

    @property
    def description(self) -> str:
        """Get step description."""
        return "Translate content to English with glossary for consistency"

    def validate_prerequisites(self, context: IPipelineContext) -> bool:
        """Validate prerequisites for translation.
        
        Args:
            context: Pipeline context
            
        Returns:
            True if prerequisites met
        """
        if not context.has("raw_html"):
            self.logger.error("Missing raw_html in context")
            return False
        
        if not context.has("detected_language"):
            self.logger.error("Missing detected_language in context")
            return False
        
        if not context.has("out_dir"):
            self.logger.error("Missing out_dir in context")
            return False
        
        return True

    def execute(self, context: IPipelineContext) -> None:
        """Execute translation step.
        
        Args:
            context: Pipeline context
            
        Raises:
            RuntimeError: If execution fails
        """
        try:
            raw_html = context.get("raw_html")
            detected_language = context.get("detected_language")
            page_count = context.get("page_count", 0)
            out_dir = context.get("out_dir")
            pdf_path = context.get("pdf_path", "")
            
            self.logger.info(f"Translating HTML content ({len(raw_html)} chars)...")
            
            # Perform translation with glossary support (HTML to HTML)
            english_html = self._translate_with_glossary(
                raw_html,
                detected_language,
                page_count
            )
            
            # Save English HTML file
            from pathlib import Path
            pdf_stem = Path(pdf_path).stem if pdf_path else "output"
            english_html_path = Path(out_dir) / f"{pdf_stem}_english.html"
            english_html_path.write_text(english_html, encoding="utf-8")
            self.logger.info(f"English HTML saved: {english_html_path}")
            
            # Extract glossary terms for reference
            glossary_terms = self._extract_glossary_terms(english_html)
            
            # Update context
            context.update({
                "english_html": english_html,
                "english_html_path": str(english_html_path),
                "glossary_terms": glossary_terms,
            })
            
            self.logger.info(
                f"Translation complete: {len(english_html)} chars, "
                f"glossary terms: {len(glossary_terms)}"
            )
            
            context.mark_step_complete(self.name)
            
        except Exception as e:
            self.logger.error(f"Translation failed: {e}")
            context.record_error(self.name, str(e))
            raise

    def rollback(self, context: IPipelineContext) -> None:
        """Rollback translation step.
        
        Args:
            context: Pipeline context
        """
        # Clean up English HTML file if created
        english_html_path = context.get("english_html_path")
        if english_html_path and Path(english_html_path).exists():
            try:
                Path(english_html_path).unlink()
                self.logger.info(f"Rolled back: {english_html_path}")
            except Exception as e:
                self.logger.warning(f"Rollback cleanup failed: {e}")
        
        context.remove("english_html")
        context.remove("english_html_path")
        context.remove("glossary_terms")

    def _translate_with_glossary(
        self,
        raw_text: str,
        lang,
        page_count: int
    ) -> str:
        """Translate HTML content to English with glossary consistency.
        
        For large documents, maintains terminology across batches.
        
        Args:
            raw_text: HTML to translate
            lang: Source language
            page_count: Number of pages
            
        Returns:
            Translated English HTML
        """
        # Direct translation - let TranslatorServiceImpl handle batching
        self.logger.info(f"Starting translation of {len(raw_text)} chars...")
        
        try:
            translated = self.translator.translate_to_english(raw_text, lang)
            
            # Extract glossary for reference
            glossary_hint = self._extract_glossary_terms(translated)
            if glossary_hint:
                self.logger.debug(f"Key terms identified: {glossary_hint}")
            
            return translated
            
        except Exception as e:
            self.logger.error(f"Translation failed: {str(e)}")
            raise

    @staticmethod
    def _extract_glossary_terms(text: str, top_k: int = 12) -> str:
        """Extract glossary terms by frequency of capitalized tokens.
        
        Args:
            text: Text to analyze
            top_k: Number of top terms to extract
            
        Returns:
            Comma-separated glossary terms
        """
        # Find capitalized tokens (likely important terms)
        tokens = re.findall(r"[A-Z][A-Za-z0-9_-]{3,}", text)
        
        if not tokens:
            return ""
        
        # Get most common terms
        common = [
            term for term, _ in Counter(tokens).most_common(top_k)
        ]
        
        return ", ".join(common)
