"""Source document formatting and normalization with bbox tracking."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from loguru import logger

from ...contracts import FormattedDocument, SentenceRegion
from .base import BaseFormatter


def build_page_offset_map(pages: List[Dict[str, Any]]) -> Dict[int, int]:
    """Build a mapping from character offset to page number.

    Returns a dict where keys are character offsets in the concatenated
    markdown and values are the corresponding page numbers.
    """
    offset_map: Dict[int, int] = {}
    offset = 0
    for page in pages:
        page_number = page.get("page_number", 0)
        offset_map[offset] = page_number
        markdown = page.get("markdown", "")
        offset += len(markdown) + 2  # +2 for "\n\n" joiner
    return offset_map


def _resolve_page(offset: int, page_map: Dict[int, int]) -> int:
    """Resolve character offset to page number via the offset map."""
    if not page_map:
        return 0
    best_page = 0
    best_offset = -1
    for map_offset, page_num in page_map.items():
        if map_offset <= offset and map_offset > best_offset:
            best_offset = map_offset
            best_page = page_num
    return best_page


def extract_sentences(
    text: str,
    page_offset_map: Optional[Dict[int, int]] = None,
) -> List[SentenceRegion]:
    """Split text into sentences and track their positions.

    Uses sentence-ending punctuation as delimiters. Each sentence
    records its page number (via ``page_offset_map``) and character
    offsets within ``text``.
    """
    if not text.strip():
        return []

    sentences: List[SentenceRegion] = []
    # Split on sentence boundaries (CJK + Western punctuation)
    pattern = re.compile(r"(?<=[。！？.!?])\s*")

    # Track split positions directly to avoid ambiguous text.find()
    last_end = 0
    for match in pattern.finditer(text):
        segment = text[last_end:match.start()].strip()
        if segment:
            page = _resolve_page(last_end, page_offset_map) if page_offset_map else 0
            sentences.append(
                SentenceRegion(
                    page=page,
                    start_offset=last_end,
                    end_offset=match.start(),
                    text=segment,
                )
            )
        last_end = match.end()

    # Capture the final segment after the last delimiter
    trailing = text[last_end:].strip()
    if trailing:
        page = _resolve_page(last_end, page_offset_map) if page_offset_map else 0
        sentences.append(
            SentenceRegion(
                page=page,
                start_offset=last_end,
                end_offset=len(text),
                text=trailing,
            )
        )

    return sentences


def _normalize_whitespace(text: str) -> str:
    """Collapse excessive blank lines and strip trailing whitespace."""
    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _fix_markdown_headings(text: str) -> str:
    """Ensure markdown headings have proper spacing."""
    text = re.sub(r"^(#{1,6})([^\s#])", r"\1 \2", text, flags=re.MULTILINE)
    return text


def _format_markdown(
    pages: List[Dict[str, Any]],
    raw_markdown: str = "",
) -> FormattedDocument:
    """Normalize and format the source document.

    Joins per-page markdown, cleans OCR artifacts, normalizes structure,
    and tracks sentence-level positions for bbox mapping.
    """
    if not raw_markdown:
        raw_markdown = "\n\n".join(
            p.get("markdown", "") for p in pages
        )

    # Basic normalization
    formatted = _normalize_whitespace(raw_markdown)
    formatted = _fix_markdown_headings(formatted)

    # Build bbox tracking
    page_offset_map = build_page_offset_map(pages)
    sentences = extract_sentences(formatted, page_offset_map)

    logger.info(
        "Formatted document: {} chars, {} sentences, {} pages",
        len(formatted),
        len(sentences),
        len(pages),
    )

    return FormattedDocument(
        formatted_markdown=formatted,
        sentences=sentences,
        metadata={"page_count": len(pages)},
    )


class MarkdownFormatter(BaseFormatter):
    """Concrete formatter implementing the BaseFormatter interface."""

    def format(self, pages: List[Dict[str, Any]]) -> FormattedDocument:
        return _format_markdown(pages)
