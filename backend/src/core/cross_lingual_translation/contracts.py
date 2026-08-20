"""Data contracts for translation and formatting pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from src.utils.text_normalize import unescape_mined_strings, unescape_mined_text


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


# ── Structured content blocks ────────────────────────────────────────────


@dataclass
class ContentBlock:
    """A single content block following MinerU content_list.json format.

    Preserves block-level document structure (titles, paragraphs, images,
    tables, equations, etc.) with bbox coordinates for structured JSON output.
    """

    type: str  # text, title, image, table, equation, code, list, header, footer, etc.
    page_idx: int = 0
    bbox: list[int] = field(default_factory=list)  # [x0, y0, x1, y1] normalized 0-1000

    # text / title fields
    text: str = ""
    text_level: int | None = None  # heading level for title type

    # image fields
    img_path: str = ""
    content: str = ""  # image description content
    image_caption: list[str] = field(default_factory=list)
    image_footnote: list[str] = field(default_factory=list)
    sub_type: str = ""  # visual sub-type for image/chart

    # table fields
    table_body: str = ""  # HTML table content
    table_caption: list[str] = field(default_factory=list)
    table_footnote: list[str] = field(default_factory=list)

    # equation fields
    text_format: str = ""  # "latex" for equations

    # code fields
    code_body: str = ""
    code_caption: list[str] = field(default_factory=list)
    code_sub_type: str = ""  # "code" or "algorithm"

    # list fields
    list_sub_type: str = ""  # "text" or "ref_text"
    list_items: list[str] = field(default_factory=list)

    # chart fields
    chart_caption: list[str] = field(default_factory=list)
    chart_footnote: list[str] = field(default_factory=list)

    # quality flags
    needs_manual_review: bool = False
    review_reason: str = ""

    # header/footer/page_number/aside_text/page_footnote
    # uses `text` field above

    def to_dict(self) -> dict[str, Any]:  # noqa  # dict-return: MinerU serialization format.
        """Serialize to MinerU content_list.json compatible format."""
        d: dict[str, Any] = {
            "type": self.type,
            "page_idx": self.page_idx,
        }
        if self.bbox:
            d["bbox"] = self.bbox

        if self.type in ("text", "title"):
            d["text"] = self.text
            if self.text_level is not None:
                d["text_level"] = self.text_level
        elif self.type == "image":
            if self.img_path:
                d["img_path"] = self.img_path
            if self.content:
                d["content"] = self.content
            if self.image_caption:
                d["image_caption"] = self.image_caption
            if self.image_footnote:
                d["image_footnote"] = self.image_footnote
            if self.sub_type:
                d["sub_type"] = self.sub_type
        elif self.type == "table":
            if self.text:
                d["text"] = self.text
            if self.img_path:
                d["img_path"] = self.img_path
            d["table_body"] = self.table_body
            if self.table_caption:
                d["table_caption"] = self.table_caption
            if self.table_footnote:
                d["table_footnote"] = self.table_footnote
        elif self.type == "equation":
            d["text"] = self.text
            d["text_format"] = self.text_format
        elif self.type == "chart":
            if self.img_path:
                d["img_path"] = self.img_path
            if self.content:
                d["content"] = self.content
            if self.chart_caption:
                d["chart_caption"] = self.chart_caption
            if self.chart_footnote:
                d["chart_footnote"] = self.chart_footnote
            if self.sub_type:
                d["sub_type"] = self.sub_type
        elif self.type == "code":
            d["code_body"] = self.code_body
            if self.code_caption:
                d["code_caption"] = self.code_caption
            if self.code_sub_type:
                d["sub_type"] = self.code_sub_type
        elif self.type == "list":
            if self.list_sub_type:
                d["sub_type"] = self.list_sub_type
            if self.list_items:
                d["list_items"] = self.list_items
        elif self.type in ("header", "footer", "page_number", "aside_text", "page_footnote"):
            d["text"] = self.text

        if self.needs_manual_review:
            d["needs_manual_review"] = True
            if self.review_reason:
                d["review_reason"] = self.review_reason

        return d

    @classmethod
    def from_mineru_block(cls, block: dict[str, Any]) -> ContentBlock:
        """Create from a MinerU content_list.json block dict."""
        block_type = block.get("type", "text")
        return cls(
            type=block_type,
            page_idx=block.get("page_idx", 0),
            bbox=block.get("bbox", []),
            text=unescape_mined_text(str(block.get("text", "") or "")),
            text_level=block.get("text_level"),
            img_path=block.get("img_path", ""),
            content=unescape_mined_text(str(block.get("content", "") or "")),
            image_caption=unescape_mined_strings(block.get("image_caption", [])),
            image_footnote=unescape_mined_strings(block.get("image_footnote", [])),
            sub_type=block.get("sub_type", "") if block_type in ("image", "chart") else "",
            table_body=unescape_mined_text(str(block.get("table_body", "") or "")),
            table_caption=unescape_mined_strings(block.get("table_caption", [])),
            table_footnote=unescape_mined_strings(block.get("table_footnote", [])),
            text_format=block.get("text_format", ""),
            code_body=unescape_mined_text(str(block.get("code_body", "") or "")),
            code_caption=unescape_mined_strings(block.get("code_caption", [])),
            code_sub_type=block.get("sub_type", "") if block_type == "code" else "",
            list_sub_type=block.get("sub_type", "") if block_type == "list" else "",
            list_items=unescape_mined_strings(block.get("list_items", [])),
            chart_caption=unescape_mined_strings(block.get("chart_caption", [])),
            chart_footnote=unescape_mined_strings(block.get("chart_footnote", [])),
        )


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
    original_blocks: List[ContentBlock] = field(default_factory=list)

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
    chunk_id: str = ""
    source_start_offset: int = -1
    source_end_offset: int = -1
    translated_start_offset: int = -1
    translated_end_offset: int = -1
    span_pairs: list[TranslationSpanPair] = field(default_factory=list)


class TranslationSpanPair(BaseModel):
    """Semantic or fallback span mapping between original and English text."""

    pair_id: str
    original_text: str
    english_text: str
    original_start_offset: int
    original_end_offset: int
    english_start_offset: int
    english_end_offset: int
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    method: Literal["semantic_llm", "deterministic_token"] = "deterministic_token"


class TranslationAlignmentChunk(BaseModel):
    """Block-level mapping from source text to English text."""

    chunk_id: str
    original_text: str
    english_text: str
    original_start_offset: int = -1
    original_end_offset: int = -1
    english_start_offset: int = -1
    english_end_offset: int = -1
    page: int = 1
    block_index: int = -1
    bbox: list[int] = Field(default_factory=list)
    span_pairs: list[TranslationSpanPair] = Field(default_factory=list)


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
    original_blocks: List[ContentBlock] = field(default_factory=list)
    translated_blocks: List[ContentBlock] = field(default_factory=list)


# ── Persistence output ─────────────────────────────────────────────────


@dataclass
class SavedDocuments:
    """Result of persisting cross-lingual documents to storage."""

    original_json_path: Path
    translated_json_path: Path
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
    original_json_path: str
    translated_json_path: str
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
    content_blocks: List[Dict[str, Any]] = Field(default_factory=list)
