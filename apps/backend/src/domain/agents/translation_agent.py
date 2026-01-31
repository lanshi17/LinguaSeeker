"""Translation Agent for bilingual text generation.

Creates aligned English-Chinese text pairs from parsed documents.
"""

from typing import List, Dict, Any
from dataclasses import dataclass

from src.infrastructure.adapters.llm_adapter import LLMAdapter, LLMRequest


@dataclass
class TranslationPair:
    """Aligned translation pair."""

    source_text: str
    target_text: str
    source_language: str
    confidence: float
    paragraph_index: int


class TranslationAgent:
    """Agent for bilingual translation generation.

    Responsibilities:
    - Detect source language
    - Generate translations (EN ↔ ZH)
    - Maintain paragraph-level alignment
    - Ensure domain terminology accuracy
    """

    def __init__(self, llm_adapter: LLMAdapter):
        """Initialize translation agent."""
        self.llm = llm_adapter

    async def process(self, markdown: str) -> List[TranslationPair]:
        """Generate translation pairs from markdown.

        Args:
            markdown: Source markdown text

        Returns:
            List of aligned translation pairs
        """
        # Split into paragraphs
        paragraphs = self._split_paragraphs(markdown)

        # Detect language
        source_lang = await self._detect_language(paragraphs[0] if paragraphs else "")

        # Generate translations
        pairs = []
        for idx, para in enumerate(paragraphs):
            if len(para.strip()) < 10:  # Skip very short paragraphs
                continue

            translation = await self._translate_paragraph(para, source_lang)

            pairs.append(
                TranslationPair(
                    source_text=para,
                    target_text=translation["text"],
                    source_language=source_lang,
                    confidence=translation["confidence"],
                    paragraph_index=idx,
                )
            )

        return pairs

    def _split_paragraphs(self, markdown: str) -> List[str]:
        """Split markdown into paragraphs."""
        # Split on double newlines
        paragraphs = markdown.split("\n\n")
        return [p.strip() for p in paragraphs if p.strip()]

    async def _detect_language(self, text: str) -> str:
        """Detect text language.

        Args:
            text: Sample text

        Returns:
            Language code (EN or ZH)
        """
        # Simple heuristic: check for Chinese characters
        chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        return "ZH" if chinese_chars > len(text) * 0.3 else "EN"

    async def _translate_paragraph(
        self, text: str, source_lang: str
    ) -> Dict[str, Any]:
        """Translate a paragraph.

        Args:
            text: Source text
            source_lang: Source language code

        Returns:
            Translation result with confidence
        """
        target_lang = "ZH" if source_lang == "EN" else "EN"

        prompt = f"""Translate the following biomedical text from {source_lang} to {target_lang}.
Preserve scientific terminology and maintain professional tone.

Text: {text}

Provide translation only, without explanations."""

        request = LLMRequest(
            prompt=prompt,
            temperature=0.3,  # Slight variation for natural translation
            max_tokens=2000,
        )

        response = await self.llm.generate(request)

        return {
            "text": response.content.strip(),
            "confidence": 0.9,  # Placeholder confidence
        }
