"""Post-processing: dedup, quality flagging, language check, block building."""

from __future__ import annotations

import re
from typing import Any, List

from loguru import logger

from ...contracts import (
    ContentBlock,
    SegmentDrift,
    TranslationSegment,
)
from .blocks import _BLOCK_SEP
from .exceptions import TranslationError
from .language_detector import _CJK_RE
from .validator.artifacts import strip_inline_artifacts
from .validator.normalize import (
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
_TRUNCATED_REF_RE = re.compile(
    r"(?:by et al\.)"
    r"|(?:In \d{1,2},\s*et al\.)"
    r"|(?:^|\.\s+)et al\.\s*\[\d+\]"
)
_TRUNCATED_YEAR_RE = re.compile(r"\bIn (\d{2}),\s")
_CYRILLIC_RE = re.compile(r"[а-яА-ЯёЁ]")
_HIRAGANA_KATAKANA_RE = re.compile(r"[ぁ-んァ-ヶ]")
_HANGUL_RE = re.compile(r"[가-힯]")

_UNTRANSLATED_BLOCK_RATIO = 0.40
_BLOCK_SOURCE_LANG_THRESHOLD = 0.15
_DEDUP_SIMILARITY_THRESHOLD = 0.75
_MIN_TRANSLATED_BLOCK_COVERAGE = 0.60
_MIN_TRANSLATED_CHAR_COVERAGE = 0.35


def trim_repetitive_content(text: str) -> str:
    """Remove repetitive heading blocks from LLM output.

    When the LLM enters a repetition loop, it generates the same section
    structure over and over. This function detects repeated heading patterns
    and keeps only the first occurrence of each heading plus its body.
    """
    paragraphs = re.split(r"\n\s*\n", text)
    seen_headings: list[str] = []
    clean_parts: list[str] = []
    current_heading: str | None = None
    current_body: list[str] = []
    removed_count = 0

    def _flush() -> None:
        """Flush the current heading+body block."""
        nonlocal removed_count
        if current_heading is None and not current_body:
            return
        block = "\n\n".join(current_body).strip() if current_body else ""
        heading_lower = current_heading.lower() if current_heading else ""
        if heading_lower and heading_lower in seen_headings:
            # Repeated heading — discard this block
            removed_count += 1 + len(current_body)
        else:
            if heading_lower:
                seen_headings.append(heading_lower)
            if current_heading is not None:
                clean_parts.append(current_heading)
            if block:
                clean_parts.append(block)

    for para in paragraphs:
        stripped = para.strip()
        heading_match = re.match(r"^(#{1,6})\s+(.+)", stripped)
        if heading_match:
            # New heading — flush previous block
            _flush()
            current_heading = stripped
            current_body = []
        else:
            if current_heading is not None:
                current_body.append(stripped)
            else:
                # Content before any heading
                clean_parts.append(stripped)

    # Flush final block
    _flush()

    if removed_count == 0:
        return text

    result = "\n\n".join(p for p in clean_parts if p).strip()
    # Safety: if trimming removed >90% of content AND result is very short,
    # keep original. This avoids false positives when the source itself is
    # short, while still catching genuine repetition in longer documents.
    if len(result) < 30 and len(result) < len(text) * 0.10:
        logger.warning(
            "Repetition trim left {} chars ({:.0f}% of original), keeping original",
            len(result),
            len(result) / max(len(text), 1) * 100,
        )
        return text

    logger.info(
        "Trimmed repetitive content: {} -> {} chars ({} paragraphs removed)",
        len(text),
        len(result),
        removed_count,
    )
    return result


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


def check_block_coverage(
    original_blocks: list[ContentBlock],
    translated_blocks: list[ContentBlock],
) -> None:
    """Reject English-but-incomplete translations that only cover a summary.

    Language checks catch untranslated source-language residue. They do not
    catch a model returning fluent English for only the title/abstract. This
    guard compares translated block/character coverage against the original
    text-like blocks before extraction consumes the document.
    """
    original_text_blocks = _translatable_text_blocks(original_blocks)
    if len(original_text_blocks) < 3:
        return

    translated_text_blocks = _translatable_text_blocks(translated_blocks)
    original_chars = sum(len(block.text.strip()) for block in original_text_blocks)
    translated_chars = sum(len(block.text.strip()) for block in translated_text_blocks)
    if original_chars == 0:
        return

    block_coverage = len(translated_text_blocks) / len(original_text_blocks)
    char_coverage = translated_chars / original_chars
    if block_coverage < _MIN_TRANSLATED_BLOCK_COVERAGE or char_coverage < _MIN_TRANSLATED_CHAR_COVERAGE:
        raise TranslationError(
            "translation_validation_failed: block_coverage — "
            f"{len(translated_text_blocks)}/{len(original_text_blocks)} text blocks "
            f"({block_coverage:.0%}) and {translated_chars}/{original_chars} chars "
            f"({char_coverage:.0%}) translated below coverage thresholds"
        )


def check_block_language(
    blocks: list[ContentBlock],
    source_language: str,
) -> None:
    """Check translated blocks for remaining source-language text.

    Catches partial translation failures where only some blocks were
    actually translated (e.g. ru doc where only the first page was
    translated, leaving 45/57 blocks in Russian).

    Raises:
        TranslationError: If >40% of text/title blocks are still in
        the source language.
    """
    if source_language in ("en", "unknown"):
        return

    # Select the appropriate source-language character detector
    if source_language == "ru":
        src_re = _CYRILLIC_RE
    elif source_language in ("zh", "ja"):
        src_re = _CJK_RE
    elif source_language == "ko":
        src_re = _HANGUL_RE
    else:
        # For es/pt/fr/de — use a simple heuristic: check if text
        # looks like it wasn't translated (high similarity to source)
        return  # Already covered by validate_translation_output

    text_blocks = [b for b in blocks if b.type in ("text", "title") and b.text.strip()]
    if not text_blocks:
        return

    untranslated = 0
    for block in text_blocks:
        text = block.text.strip()
        if not text:
            continue
        src_chars = len(src_re.findall(text))
        ratio = src_chars / max(len(text), 1)
        if ratio > _BLOCK_SOURCE_LANG_THRESHOLD:
            untranslated += 1

    total = len(text_blocks)
    if total == 0:
        return
    ratio = untranslated / total
    if ratio > _UNTRANSLATED_BLOCK_RATIO:
        raise TranslationError(
            f"translation_validation_failed: per_block_check — "
            f"{untranslated}/{total} blocks still in {source_language} "
            f"({ratio:.0%} > {_UNTRANSLATED_BLOCK_RATIO:.0%} threshold)"
        )
    if untranslated > 0:
        logger.warning(
            "Per-block language check: {}/{} blocks still in {} ({:.0f}%)",
            untranslated,
            total,
            source_language,
            ratio * 100,
        )


def deduplicate_bilingual_blocks(
    blocks: list[ContentBlock],
) -> list[ContentBlock]:
    """Remove duplicate blocks from bilingual documents.

    In bilingual documents (e.g. zh with English abstract), adjacent
    text blocks may contain the same content in two languages. After
    translation both become English, creating near-duplicate blocks.

    This method detects adjacent text/title blocks with high token
    overlap and removes the duplicate, keeping the first occurrence.
    """
    if len(blocks) < 2:
        return blocks

    def _tokens(text: str) -> set[str]:
        """Extract lowercase alphanumeric tokens for comparison."""
        return set(re.findall(r"[a-z0-9]+", text.lower()))

    result: list[ContentBlock] = []
    removed = 0
    for i, block in enumerate(blocks):
        if block.type not in ("text", "title") or not block.text.strip():
            result.append(block)
            continue

        # Check against the previous text block in result
        prev = result[-1] if result else None
        if prev and prev.type in ("text", "title") and prev.text.strip():
            tokens_cur = _tokens(block.text)
            tokens_prev = _tokens(prev.text)
            if tokens_cur and tokens_prev:
                overlap = len(tokens_cur & tokens_prev) / max(
                    len(tokens_cur | tokens_prev),
                    1,
                )
                if overlap > _DEDUP_SIMILARITY_THRESHOLD:
                    # Keep the longer block (likely the translated one)
                    if len(block.text) > len(prev.text):
                        result[-1] = block
                    removed += 1
                    continue

        result.append(block)

    if removed:
        logger.info(
            "Deduplicated {} bilingual block pairs ({} → {})",
            removed,
            len(blocks),
            len(result),
        )
    return result


def flag_quality_issues(blocks: list[ContentBlock]) -> int:
    """Flag blocks that need manual review due to quality issues.

    Detects truncated references, ambiguous pronouns, and other
    patterns that indicate OCR/translation problems.

    Returns the number of blocks flagged.
    """
    flagged = 0
    for block in blocks:
        if block.type not in ("text", "title"):
            continue
        text = block.text
        reasons: list[str] = []

        # Truncated references: "et al. [12]" with no author/year
        if _TRUNCATED_REF_RE.search(text):
            reasons.append("truncated reference (missing author/year)")

        # Truncated 2-digit years: "In 20," instead of "In 2020,"
        year_match = _TRUNCATED_YEAR_RE.search(text)
        if year_match:
            reasons.append(f"truncated year ({year_match.group(1)} digits)")

        # Ambiguous pronoun "including that" without clear antecedent
        if re.search(r"including that[,;.\s]", text):
            reasons.append("ambiguous pronoun 'including that' — should spell out noun (e.g. 'including ERT')")

        # "suspicious pathogenic" — should be "suspected pathogenic variant"
        if re.search(r"\bsuspicious\b", text, re.I):
            reasons.append("'suspicious' should be 'suspected' in medical English")

        if reasons:
            block.needs_manual_review = True
            block.review_reason = "; ".join(reasons)
            flagged += 1

    return flagged


def compute_translation_drift(
    source_segments: List[str],
    translated_parts: List[str],
) -> List[SegmentDrift]:
    """Compute character drift between source and translated segments.

    For each segment pair, tracks the offset positions and length changes.
    """
    drifts: list[SegmentDrift] = []
    source_offset = 0
    translated_offset = 0

    for idx in range(max(len(source_segments), len(translated_parts))):
        src = source_segments[idx] if idx < len(source_segments) else ""
        tr = translated_parts[idx] if idx < len(translated_parts) else ""
        src_len = len(src)
        tr_len = len(tr)
        length_drift = tr_len - src_len

        drifts.append(
            SegmentDrift(
                segment_index=idx,
                source_start=source_offset,
                source_end=source_offset + src_len,
                translated_start=translated_offset,
                translated_end=translated_offset + tr_len,
                source_length=src_len,
                translated_length=tr_len,
                length_drift=length_drift,
                source_text=src[:200],  # Truncate for JSON readability
                translated_text=tr[:200],
            )
        )
        source_offset += src_len + 2  # +2 for "\n\n" joiner
        translated_offset += tr_len + 2

    return drifts
