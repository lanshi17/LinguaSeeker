"""Post-processing: dedup, quality flagging, language check, block building."""

from __future__ import annotations

import re

from loguru import logger

from ...contracts import (
    ContentBlock,
)
from .blocks import _translatable_text_blocks
from ..exceptions import TranslationError
from ..language_detector import _CJK_RE

# Pre-compiled patterns
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