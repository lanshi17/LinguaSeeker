"""Source document formatting and normalization with bbox tracking."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from loguru import logger

from ...contracts import (
    ContentBlock,
    FormattedDocument,
    SentenceDrift,
    SentenceRegion,
)
from .base import BaseFormatter

_HTML_DETECT_RE = re.compile(r"^\s*<(!DOCTYPE|html|head|body|title)\b", re.IGNORECASE | re.DOTALL)


def _is_html(text: str) -> bool:
    """Return True if text looks like an HTML document."""
    return bool(_HTML_DETECT_RE.match(text[:500]))


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


def _find_raw_offset(
    sentence_text: str,
    raw_text: str,
    search_start: int,
) -> tuple[int, int]:
    """Find a sentence's position in the raw text by searching for its content.

    Returns (start, end) offsets in raw_text, or (-1, -1) if not found.
    """
    # Try exact match first
    idx = raw_text.find(sentence_text, search_start)
    if idx != -1:
        return (idx, idx + len(sentence_text))

    # Try normalized match (collapse whitespace differences)
    normalized = re.sub(r"\s+", " ", sentence_text.strip())
    for i in range(search_start, len(raw_text) - len(normalized) + 1):
        candidate = re.sub(r"\s+", " ", raw_text[i : i + len(sentence_text) + 20].strip())
        if candidate.startswith(normalized[:50]):
            # Found approximate match
            end = min(i + len(sentence_text), len(raw_text))
            return (i, end)

    return (-1, -1)


def compute_format_drift(
    raw_text: str,
    formatted_sentences: List[SentenceRegion],
) -> List[SentenceDrift]:
    """Compute character drift between raw and formatted text for each sentence.

    For each sentence in the formatted text, finds its corresponding position
    in the raw text and calculates the offset drift.
    """
    drifts: List[SentenceDrift] = []
    search_start = 0

    for idx, sent in enumerate(formatted_sentences):
        raw_start, raw_end = _find_raw_offset(sent.text, raw_text, search_start)
        if raw_start == -1:
            # Fallback: use proportional mapping
            ratio = sent.start_offset / max(len(raw_text), 1)
            raw_start = int(ratio * len(raw_text))
            raw_end = raw_start + len(sent.text)

        drift = sent.start_offset - raw_start
        drifts.append(
            SentenceDrift(
                sentence_index=idx,
                page=sent.page,
                raw_start=raw_start,
                raw_end=raw_end,
                formatted_start=sent.start_offset,
                formatted_end=sent.end_offset,
                drift=drift,
                text=sent.text,
            )
        )
        search_start = raw_end

    return drifts


def _format_markdown(
    pages: List[Dict[str, Any]],
    raw_markdown: str = "",
    content_blocks: List[Dict[str, Any]] | None = None,
) -> FormattedDocument:
    """Normalize and format the source document.

    Joins per-page markdown, cleans OCR artifacts, normalizes structure,
    and tracks sentence-level positions for bbox mapping.
    """
    if not raw_markdown:
        raw_markdown = "\n\n".join(
            p.get("markdown", "") for p in pages
        )

    raw_copy = raw_markdown  # Preserve for drift computation

    # Basic normalization
    formatted = _normalize_whitespace(raw_markdown)
    formatted = _fix_markdown_headings(formatted)

    # Build bbox tracking
    page_offset_map = build_page_offset_map(pages)
    sentences = extract_sentences(formatted, page_offset_map)

    # Build structured blocks from MinerU content_list
    blocks = [ContentBlock.from_mineru_block(b) for b in (content_blocks or [])]

    logger.info(
        "Formatted document: {} chars, {} sentences, {} pages, {} blocks",
        len(formatted),
        len(sentences),
        len(pages),
        len(blocks),
    )

    return FormattedDocument(
        formatted_markdown=formatted,
        sentences=sentences,
        metadata={"page_count": len(pages)},
        raw_markdown=raw_copy,
        original_blocks=blocks,
    )


class MarkdownFormatter(BaseFormatter):
    """Concrete formatter implementing the BaseFormatter interface."""

    def __init__(self, llm: Any = None):
        """Initialize formatter with optional LLM for enhanced formatting.

        Args:
            llm: Optional LLM instance for redaction detection and OCR repair.
                 When provided, the formatter will use LLM to identify missing
                 values and insert [REDACTED] markers.
        """
        self._llm = llm

    def format(
        self,
        pages: List[Dict[str, Any]],
        content_blocks: List[Dict[str, Any]] | None = None,
    ) -> FormattedDocument:
        doc = _format_markdown(pages, content_blocks=content_blocks)
        if self._llm and doc.formatted_markdown.strip():
            doc = self._apply_llm_formatting(doc)
        return doc

    def _apply_llm_formatting(self, doc: FormattedDocument) -> FormattedDocument:
        """Use LLM to detect redactions and repair OCR artifacts."""
        from ..translate.prompts import get_format_prompt

        prompt = get_format_prompt(doc.formatted_markdown)
        logger.info("LLM formatting: {} chars", len(doc.formatted_markdown))

        try:
            # Use the translator's LLM invocation with retry
            from langchain_core.messages import HumanMessage
            response = self._llm.invoke([HumanMessage(content=prompt)])
            formatted = response.content if hasattr(response, 'content') else str(response)

            if _is_html(formatted):
                logger.warning("LLM format output is HTML (likely error page), keeping original")
                return doc

            # Safety: if output is too different in length, keep original
            if abs(len(formatted) - len(doc.formatted_markdown)) > len(doc.formatted_markdown) * 0.3:
                logger.warning(
                    "LLM format output length mismatch ({} vs {} chars), keeping original",
                    len(formatted), len(doc.formatted_markdown),
                )
                return doc

            # Count [REDACTED] markers added
            orig_count = doc.formatted_markdown.count("[REDACTED]")
            new_count = formatted.count("[REDACTED]")
            if new_count > orig_count:
                logger.info("LLM format added {} [REDACTED] markers", new_count - orig_count)

            # Update document with LLM-formatted text
            from .formatter import extract_sentences, build_page_offset_map
            page_offset_map = build_page_offset_map(
                [{"page_number": i, "markdown": ""} for i in range(doc.metadata.get("page_count", 1))]
            )
            sentences = extract_sentences(formatted, page_offset_map)

            return FormattedDocument(
                formatted_markdown=formatted,
                sentences=sentences,
                metadata=doc.metadata,
                raw_markdown=doc.raw_markdown,
                original_blocks=doc.original_blocks,
            )
        except Exception as exc:
            logger.warning("LLM formatting failed: {}, keeping original", exc)
            return doc

    def compute_drift(
        self,
        raw_text: str,
        formatted_sentences: List[SentenceRegion],
    ) -> List[SentenceDrift]:
        """Compute format drift for the given sentences."""
        return compute_format_drift(raw_text, formatted_sentences)
