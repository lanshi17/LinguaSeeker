"""Data contracts for translation and formatting pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


# ── Bbox tracking ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class BboxPoint:
    """Position reference: page number + character offset within page."""

    page: int
    offset: int


@dataclass(frozen=True)
class SentenceRegion:
    """Sentence-level position tracking within a document."""

    page: int
    start_offset: int
    end_offset: int
    text: str

    @property
    def span(self) -> int:
        return self.end_offset - self.start_offset


# ── Formatting output ────────────────────────────────────────────────────


@dataclass
class FormattedDocument:
    """Output of the format/normalize stage.

    ``formatted_markdown`` is the authoritative source-language document.
    ``sentences`` tracks each sentence's origin for bbox mapping.
    """

    formatted_markdown: str
    sentences: List[SentenceRegion] = field(default_factory=list)
    source_language: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_pages(
        cls,
        pages: List[Dict[str, Any]],
        formatted_markdown: str,
        source_language: str = "",
    ) -> FormattedDocument:
        """Build from upstream page dicts (``ParseResult.pages`` serialized)."""
        return cls(
            formatted_markdown=formatted_markdown,
            source_language=source_language,
            metadata={"page_count": len(pages)},
        )


# ── Translation output ───────────────────────────────────────────────────


@dataclass
class TranslationSegment:
    """One translated segment with its bbox mapping back to the formatted source."""

    index: int
    source_text: str
    translated_text: str
    source_bbox: Optional[SentenceRegion] = None
    translated_bbox: Optional[SentenceRegion] = None


@dataclass
class TranslationResult:
    """Final output of the full format → translate pipeline.

    ``formatted_original`` — the authoritative source-language document.
    ``translated_english`` — the authoritative English document.
    """

    formatted_original: str
    translated_english: str
    source_language: str
    terminology_map: Dict[str, str]
    translation_warnings: List[str]
    sentences: List[SentenceRegion]
    segments: List[TranslationSegment]


# ── Pipeline state (LangGraph) ─────────────────────────────────────────


class PipelineState(BaseModel):
    """Typed state for the LangGraph pipeline — replaces free-form dict.

    Each field is a discrete pipeline artifact. Nodes declare what they
    read/write via their function signatures.
    """

    model_config = {"arbitrary_types_allowed": True}

    pages: List[Dict[str, Any]]
    formatted: Optional[FormattedDocument] = None
    source_language: str = ""
    needs_translation: bool = True
    translation_result: Optional[TranslationResult] = None
