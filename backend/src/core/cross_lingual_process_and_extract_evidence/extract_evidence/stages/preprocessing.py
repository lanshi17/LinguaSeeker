"""Preprocessing: normalise raw evidence, apply per-field truncation."""

from __future__ import annotations

import re
from dataclasses import replace

from ..contracts import ExtractedEvidence


def _normalise_whitespace(text: str) -> str:
    """Collapse runs of whitespace (including newlines) into a single space."""
    return re.sub(r"\s+", " ", text).strip()


def _truncate(text: str, limit: int) -> str:
    """Truncate to *limit* chars, preserving whole words where possible."""
    if len(text) <= limit:
        return text
    truncated = text[:limit]
    last_space = truncated.rfind(" ")
    if last_space > limit * 0.8:
        truncated = truncated[:last_space]
    return truncated + "…"


class EvidencePreprocessor:
    """Normalise and truncate evidence fields."""

    def __init__(
        self,
        article_limit: int = 3000,
        paragraph_limit: int = 800,
        sentence_limit: int = 400,
    ) -> None:
        self._article_limit = article_limit
        self._paragraph_limit = paragraph_limit
        self._sentence_limit = sentence_limit

    def apply(self, evidence: ExtractedEvidence) -> ExtractedEvidence:
        texts = evidence.texts
        if not texts:
            return evidence

        def clean(text: str, limit: int) -> str:
            return _truncate(_normalise_whitespace(text), limit)

        return replace(
            evidence,
            article_title=clean(texts.article_title, self._article_limit),
            article_abstract=clean(texts.article_abstract, self._article_limit),
            article_keywords=clean(texts.article_keywords, self._paragraph_limit),
            paragraph_text=clean(texts.paragraph_text, self._paragraph_limit),
            paragraph_location=clean(texts.paragraph_location, self._sentence_limit),
            figure_caption=clean(texts.figure_caption, self._paragraph_limit),
            table_caption=clean(texts.table_caption, self._paragraph_limit),
            table_data=clean(texts.table_data, self._paragraph_limit),
            supplementary_info=clean(texts.supplementary_info, self._article_limit),
        )
