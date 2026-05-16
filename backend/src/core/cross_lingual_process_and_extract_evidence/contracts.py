"""Data contracts for translation and formatting pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Bbox tracking ────────────────────────────────────────────────────────


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


# ── Character drift tracking ─────────────────────────────────────────────


@dataclass(frozen=True)
class SentenceDrift:
    """Character drift for one sentence: raw OCR → formatted position."""

    sentence_index: int
    page: int
    raw_start: int
    raw_end: int
    formatted_start: int
    formatted_end: int
    drift: int  # formatted_start - raw_start
    text: str


@dataclass(frozen=True)
class SegmentDrift:
    """Character drift for one translation segment: source → translated position."""

    segment_index: int
    source_start: int
    source_end: int
    translated_start: int
    translated_end: int
    source_length: int
    translated_length: int
    length_drift: int  # translated_length - source_length
    source_text: str
    translated_text: str


@dataclass
class OriginalLayoutReport:
    """Layout and character drift report for the formatted original text."""

    doc_id: str = ""
    source_language: str = ""
    raw_text_length: int = 0
    formatted_text_length: int = 0
    sentence_count: int = 0
    page_count: int = 0
    sentences: List[Dict[str, Any]] = field(default_factory=list)
    format_drifts: List[SentenceDrift] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "metadata": {
                "doc_id": self.doc_id,
                "source_language": self.source_language,
                "raw_text_length": self.raw_text_length,
                "formatted_text_length": self.formatted_text_length,
                "sentence_count": self.sentence_count,
                "page_count": self.page_count,
            },
            "sentences": self.sentences,
            "format_drifts": [
                {
                    "sentence_index": d.sentence_index,
                    "page": d.page,
                    "raw_start": d.raw_start,
                    "raw_end": d.raw_end,
                    "formatted_start": d.formatted_start,
                    "formatted_end": d.formatted_end,
                    "drift": d.drift,
                    "text": d.text[:200],  # Truncate for readability
                }
                for d in self.format_drifts
            ],
        }


@dataclass
class TranslatedLayoutReport:
    """Layout and character drift report for the translated text."""

    doc_id: str = ""
    source_language: str = ""
    formatted_text_length: int = 0
    translated_text_length: int = 0
    segment_count: int = 0
    terminology_map: Dict[str, str] = field(default_factory=dict)
    translation_warnings: List[str] = field(default_factory=list)
    segments: List[Dict[str, Any]] = field(default_factory=list)
    translation_drifts: List[SegmentDrift] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "metadata": {
                "doc_id": self.doc_id,
                "source_language": self.source_language,
                "formatted_text_length": self.formatted_text_length,
                "translated_text_length": self.translated_text_length,
                "segment_count": self.segment_count,
                "terminology_count": len(self.terminology_map),
                "warning_count": len(self.translation_warnings),
            },
            "terminology_map": self.terminology_map,
            "translation_warnings": self.translation_warnings,
            "segments": self.segments,
            "translation_drifts": [
                {
                    "segment_index": d.segment_index,
                    "source_start": d.source_start,
                    "source_end": d.source_end,
                    "translated_start": d.translated_start,
                    "translated_end": d.translated_end,
                    "source_length": d.source_length,
                    "translated_length": d.translated_length,
                    "length_drift": d.length_drift,
                    "source_text": d.source_text[:200],
                    "translated_text": d.translated_text[:200],
                }
                for d in self.translation_drifts
            ],
        }


# ── Formatting output ────────────────────────────────────────────────────


@dataclass
class FormattedDocument:
    """Output of the format/normalize stage.

    ``formatted_markdown`` is the authoritative source-language document.
    ``sentences`` tracks each sentence's origin for bbox mapping.
    ``raw_markdown`` preserves the original text for drift computation.
    """

    formatted_markdown: str
    sentences: List[SentenceRegion] = field(default_factory=list)
    source_language: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    raw_markdown: str = ""

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


# ── Persistence output ─────────────────────────────────────────────────


@dataclass
class SavedDocuments:
    """Result of persisting cross-lingual documents to storage."""

    original_md_path: Path
    translated_md_path: Path
    metadata_path: Path
    image_dir: Path
    image_paths: list[Path]
    output_dir: Path
    created_at: datetime


class CrossLingualOutput(BaseModel):
    """Typed output contract passed to downstream modules.

    This is the authoritative schema that Phase 3 (standardize entities)
    receives from Phase 2 (cross-lingual processing).
    """

    formatted_original: str
    translated_english: str
    source_language: str
    terminology_map: Dict[str, str]
    translation_warnings: list[str]
    output_dir: str
    original_md_path: str
    translated_md_path: str
    image_paths: list[str]


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
    image_paths: list[str] = Field(default_factory=list)
