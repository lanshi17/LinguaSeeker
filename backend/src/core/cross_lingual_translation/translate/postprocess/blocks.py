"""Post-processing: dedup, quality flagging, language check, block building."""

from __future__ import annotations

import re
from typing import Any, List

from loguru import logger

from ...contracts import (
    ContentBlock,
    TranslationSegment,
)
from ..blocks import _BLOCK_SEP
from ..validator.artifacts import strip_inline_artifacts
from ..validator.normalize import (
    fix_email_placeholder,
    fix_ocr_truncations,
    fix_word_boundary_redacted,
    normalize_cjk_punctuation,
    normalize_placeholders,
)

# Pre-compiled patterns
_DOI_RE = re.compile(
    r"(?:DOI|doi)\s*[:\s：]*\d+\.\d+/"
    r"|https?://doi\.org/"
    r"|https?://dx\.doi\.org/"
)

def fallback_block_text(
    block: ContentBlock,
    segments: List[TranslationSegment],
) -> str:
    """Fallback: find translated text via segment matching."""
    block_text = block.text.strip()
    if not block_text:
        return ""
    for seg in segments:
        src = seg.source_text.strip()
        if not src:
            continue
        src_start = src[: max(len(block_text) * 2, 100)]
        if src in block_text or block_text in src_start:
            return seg.translated_text
    return ""


def build_translated_blocks(
    original_blocks: List[ContentBlock],
    segments: List[TranslationSegment],
    translated_text: str,
    text_block_indices: list[int] | None = None,
    aux_translations: dict[int, dict[str, Any]] | None = None,
) -> List[ContentBlock]:
    """Map translated text back to original block structure.

    When the source text was built from blocks joined with _BLOCK_SEP,
    the translated text can be split on the same delimiter to recover
    per-block translations. Falls back to segment matching if the
    delimiter is not found.

    Args:
        original_blocks: The original content blocks.
        segments: Translation segments (used for fallback).
        translated_text: The full translated text (may contain delimiters).
        text_block_indices: Indices of blocks that were included in the
            marked text (non-empty text/title blocks).
        aux_translations: Optional dict of auxiliary field translations
            keyed by block index.
    """
    sep = _BLOCK_SEP
    idx_map: dict[int, str] = {}

    # Try delimiter-based split first
    if sep in translated_text:
        parts = translated_text.split(sep)
        # Clean up residual markers and empty pieces
        pieces = []
        for p in parts:
            cleaned = p.replace(sep.strip(), "").strip()
            cleaned = strip_inline_artifacts(cleaned)
            if cleaned:
                pieces.append(cleaned)
        indices = text_block_indices or []
        for j, piece in enumerate(pieces):
            if j < len(indices):
                idx_map[indices[j]] = piece
        logger.info(
            "Split translated text on block delimiter: {} pieces from {} blocks",
            len(pieces),
            len(original_blocks),
        )

    # Count text/title blocks for single-block shortcut
    # Include footer blocks with DOI information as they are also text-based
    text_blocks = [
        b for b in original_blocks if b.type in ("text", "title") or (b.type == "footer" and _DOI_RE.search(b.text))
    ]

    # Block types that are not body text — filter from downstream output
    # Exception: footer blocks containing DOI information are preserved
    _NON_BODY_TYPES = {"header", "footer", "page_number"}

    translated_blocks: list[ContentBlock] = []
    empty_count = 0
    filtered_non_body = 0
    doi_blocks_preserved = 0
    for i, block in enumerate(original_blocks):
        # Filter non-body blocks (headers, footers, page numbers)
        # but preserve footer blocks containing DOI information
        if block.type in _NON_BODY_TYPES:
            # Check if this footer block contains DOI information
            if block.type == "footer" and _DOI_RE.search(block.text):
                doi_blocks_preserved += 1
                # Preserve DOI footer as-is (no translation needed)
                translated_blocks.append(
                    ContentBlock(
                        type=block.type,
                        page_idx=block.page_idx,
                        bbox=block.bbox,
                        text=block.text,
                    )
                )
                continue
            filtered_non_body += 1
            continue

        # Handle text/title blocks AND footer blocks with DOI information
        if block.type in ("text", "title") or (block.type == "footer" and _DOI_RE.search(block.text)):
            if i in idx_map:
                new_text = idx_map[i]
            elif len(text_blocks) == 1 and translated_text.strip():
                # Single text block, no delimiter — use full translation
                new_text = translated_text.strip()
            else:
                new_text = fallback_block_text(
                    block,
                    segments,
                )
            # Filter empty text/title blocks
            if not new_text.strip():
                empty_count += 1
                continue
            # Safety: strip any residual «BLK» markers that the LLM may have
            # echoed inside a block's text (not as a structural separator)
            new_text = new_text.replace("«BLK»", "").strip()
            # Per-block post-processing (placeholders, punctuation, email, OCR)
            new_text = normalize_placeholders(new_text)
            new_text = normalize_cjk_punctuation(new_text)
            new_text = fix_email_placeholder(new_text)
            new_text = fix_ocr_truncations(new_text)
            new_text = fix_word_boundary_redacted(new_text)
            new_block = ContentBlock(
                type=block.type,
                page_idx=block.page_idx,
                bbox=block.bbox,
                text=new_text,
                text_level=block.text_level if block.type in ("text", "title") else None,
            )
        else:
            # Non-text blocks: copy with aux translations if available
            aux = (aux_translations or {}).get(i, {})
            content = block.content
            sub_type = block.sub_type

            # Strip Mermaid diagrams from image blocks — these are
            # LLM-generated reconstructions, not original content.
            # Keep only the image and caption for downstream.
            needs_review = False
            review_reason = ""
            if sub_type == "flowchart" and "mermaid" in (content or "").lower():
                content = ""
                sub_type = "pedigree"
                needs_review = True
                review_reason = "Mermaid structure does not represent pedigree topology"

            new_block = ContentBlock(
                type=block.type,
                page_idx=block.page_idx,
                bbox=block.bbox,
                text=block.text,
                img_path=block.img_path,
                content=content,
                image_caption=aux.get("image_caption", list(block.image_caption)),
                image_footnote=aux.get("image_footnote", list(block.image_footnote)),
                sub_type=sub_type,
                table_body=block.table_body,
                table_caption=aux.get("table_caption", list(block.table_caption)),
                table_footnote=aux.get("table_footnote", list(block.table_footnote)),
                text_format=block.text_format,
                code_body=block.code_body,
                code_caption=list(block.code_caption),
                code_sub_type=block.code_sub_type,
                list_sub_type=block.list_sub_type,
                list_items=list(block.list_items),
                chart_caption=list(block.chart_caption),
                chart_footnote=list(block.chart_footnote),
                needs_manual_review=needs_review,
                review_reason=review_reason,
            )
        translated_blocks.append(new_block)

    if empty_count:
        logger.info("Filtered {} empty text/title blocks", empty_count)
    if filtered_non_body:
        logger.info("Filtered {} non-body blocks (header/footer/page_number)", filtered_non_body)
    if doi_blocks_preserved:
        logger.info("Preserved {} footer blocks containing DOI information", doi_blocks_preserved)
    logger.info(
        "Block mapping: {} original → {} translated ({} filtered: {} non-body + {} empty)",
        len(original_blocks),
        len(translated_blocks),
        filtered_non_body + empty_count,
        filtered_non_body,
        empty_count,
    )
    return translated_blocks


def _translatable_text_blocks(blocks: list[ContentBlock]) -> list[ContentBlock]:
    """Return text-like body blocks expected to have translated counterparts."""
    return [block for block in blocks if block.type in ("text", "title") and block.text.strip()]