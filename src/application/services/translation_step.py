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
    - raw_text: Text to translate
    - detected_language: Source language
    - page_count: Number of pages (for optimization)
    
    Output context keys:
    - english_markdown: Translated English content
    - glossary_terms: Extracted key terminology
    """

    def __init__(self, translator: TranslatorService):
        """Initialize translation step.
        
        Args:
            translator: Translation service
        """
        self.translator = translator
        self.logger = Logger.get_logger(__name__)
        self.max_chunk_size = 4000  # characters per chunk

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
        if not context.has("raw_text") and not context.has("english_markdown"):
            self.logger.error("Missing raw_text in context")
            return False
        
        if not context.has("detected_language"):
            self.logger.error("Missing detected_language in context")
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
            raw_text = context.get("raw_text")
            detected_language = context.get("detected_language")
            page_count = context.get("page_count", 0)

            # If MinerU already produced English content, reuse it and skip translation
            if not raw_text and context.has("english_markdown"):
                english_markdown = context.get("english_markdown") or ""
                glossary_terms = self._extract_glossary_terms(english_markdown)
                context.update({
                    "english_markdown": english_markdown,
                    "glossary_terms": glossary_terms,
                })
                self.logger.info("English content already present; skipping translation")
                context.mark_step_complete(self.name)
                return
            
            self.logger.info(f"Translating content ({len(raw_text)} chars)...")
            
            # Perform translation with glossary support
            english_markdown = self._translate_with_glossary(
                raw_text,
                detected_language,
                page_count
            )
            
            # Extract glossary terms for reference
            glossary_terms = self._extract_glossary_terms(english_markdown)
            
            # Update context
            context.update({
                "english_markdown": english_markdown,
                "glossary_terms": glossary_terms,
            })
            
            self.logger.info(
                f"Translation complete: {len(english_markdown)} chars, "
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
        context.remove("english_markdown")
        context.remove("glossary_terms")

    def _translate_with_glossary(
        self,
        raw_text: str,
        lang,
        page_count: int
    ) -> str:
        """Translate content to English; for large docs, split and reuse glossary.
        
        Args:
            raw_text: Text to translate
            lang: Source language
            page_count: Number of pages
            
        Returns:
            Translated English markdown
        """
        # For short content, direct translation
        if len(raw_text) < self.max_chunk_size:
            return self.translator.translate_to_english(raw_text, lang)

        self.logger.info("Large document detected; using chunked translation...")
        
        # Split content for manageable processing
        segments = self._split_content(raw_text)
        
        glossary_hint = ""
        translated_segments = []
        
        for idx, segment in enumerate(segments):
            # Add glossary hint to maintain consistency
            segment_with_glossary = segment
            if glossary_hint:
                segment_with_glossary = (
                    f"Glossary (keep terminology consistent): {glossary_hint}\n\n" +
                    segment
                )
            
            self.logger.info(f"Translating segment {idx + 1}/{len(segments)}...")
            translated = self.translator.translate_to_english(
                segment_with_glossary,
                lang
            )
            translated_segments.append(translated)
            
            # Update glossary from first segment
            if idx == 0:
                glossary_hint = self._extract_glossary_terms(translated)
                self.logger.debug(f"Glossary extracted: {glossary_hint}")
        
        result = "\n\n---\n\n".join(translated_segments)
        return result

    def _split_content(self, text: str) -> List[str]:
        """Split content into manageable chunks.
        
        Args:
            text: Text to split
            
        Returns:
            List of text segments
        """
        # Try to split by page delimiter
        splitter = "\n\n---\n\n"
        if splitter in text:
            return text.split(splitter)
        
        # Fall back to fixed-size chunks
        return [
            text[i:i + self.max_chunk_size]
            for i in range(0, len(text), self.max_chunk_size)
        ]

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
