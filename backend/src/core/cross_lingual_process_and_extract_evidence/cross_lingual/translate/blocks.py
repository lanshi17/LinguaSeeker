"""Block-level merge, split, and marker operations for translation."""
from __future__ import annotations

import re
from typing import Dict, Tuple

from loguru import logger

from ...contracts import ContentBlock
from .language_detector import _CJK_RE
from .validator.redacted import mark_redacted_values

_BLOCK_SEP = "\n\n«BLK»\n\n"
_BLOCK_MARKER_RE = re.compile(r"\[BLOCK_(\d+)\]")
_SHORT_KW_CJK_RE = re.compile(r"[一-鿿]")
_KW_MERGE_SEP = "；"


def is_predominantly_english(text: str) -> bool:
    """Check if text is predominantly English (low CJK ratio)."""
    cjk_count = len(_CJK_RE.findall(text))
    total = len(text.strip()) or 1
    return cjk_count / total < 0.05


def is_short_keyword(text: str) -> bool:
    """Check if text is a short isolated keyword (1-4 CJK chars).

    Short keyword blocks (e.g. "古菌", "硫化叶菌", "重组") are
    vulnerable to context pollution when the LLM fills them with
    nearby content. These should be merged before translation.
    """
    stripped = text.strip()
    if not stripped:
        return False
    cjk_chars = _SHORT_KW_CJK_RE.findall(stripped)
    return 1 <= len(cjk_chars) <= 4 and len(stripped) <= 10


def merge_short_keywords(
    non_empty: list[tuple[int, ContentBlock]],
) -> Tuple[
    list[tuple[int, ContentBlock]],
    Dict[int, int],
]:
    """Merge adjacent short keyword blocks into single blocks.

    When the LLM translates isolated 1-4 char CJK keyword blocks,
    it often fills them with nearby content (context pollution).
    This merges adjacent short keywords into one block (joined with
    ``；``) so the LLM sees a meaningful phrase to translate.

    Returns:
        Tuple of (merged_blocks, merge_map). ``merge_map[i]`` is the
        number of original blocks merged into output block ``i``.
        A value of 1 means no merge; value >1 means N blocks were
        merged.
    """
    if not non_empty:
        return [], {}

    merged: list[tuple[int, ContentBlock]] = []
    merge_map: dict[int, int] = {}
    run_indices: list[int] = []  # original block_indices in current run
    run_texts: list[str] = []

    def _flush_run() -> None:
        if not run_indices:
            return
        if len(run_indices) >= 2:
            # Merge: join texts, keep first block_idx
            combined = _KW_MERGE_SEP.join(run_texts)
            merged.append((
                run_indices[0],
                ContentBlock(type="text", text=combined),
            ))
            merge_map[len(merged) - 1] = len(run_indices)
        else:
            # Single — not merged, pass through original
            merged.append(non_empty[run_indices[0]])
            merge_map[len(merged) - 1] = 1
        run_indices.clear()
        run_texts.clear()

    for i, (block_idx, block) in enumerate(non_empty):
        text = block.text.strip()
        if is_short_keyword(text):
            run_indices.append(i)
            run_texts.append(text)
        else:
            _flush_run()
            merged.append((block_idx, block))
            merge_map[len(merged) - 1] = 1
    _flush_run()

    logger.info(
        "Keyword merge: {} blocks → {} blocks ({} groups merged)",
        len(non_empty), len(merged),
        sum(1 for v in merge_map.values() if v > 1),
    )
    return merged, merge_map


def split_merged_keywords(
    translated_parts: list[str],
    merge_map: Dict[int, int],
) -> list[str]:
    """Split merged keyword blocks back into individual translations.

    After translation, merged keyword blocks (joined with ``；``)
    are split back into individual keyword translations. If the
    LLM used a different separator (e.g. "; " or ", "), we detect
    that and split accordingly.

    Args:
        translated_parts: Translated text per merged block.
        merge_map: From ``merge_short_keywords`` — maps output index
            to number of original blocks merged.

    Returns:
        Expanded list with one entry per original block.
    """
    result: list[str] = []
    for i, text in enumerate(translated_parts):
        count = merge_map.get(i, 1)
        if count <= 1:
            result.append(text)
            continue

        # Try splitting on common separators the LLM might use
        # Order: ；(original), ; (ASCII), , (comma)
        parts: list[str] | None = None
        for sep in ("；", "; ", ", "):
            candidate = [p.strip() for p in text.split(sep) if p.strip()]
            if len(candidate) == count:
                parts = candidate
                break

        if parts:
            result.extend(parts)
        else:
            # Can't split cleanly — keep merged text in first slot,
            # fill remaining with empty
            result.append(text)
            result.extend([""] * (count - 1))
            logger.warning(
                "Could not split merged keyword block {} (expected {} parts): {}",
                i, count, text[:60],
            )
    return result


def join_blocks_with_markers(
    non_empty: list[tuple[int, ContentBlock]],
) -> Tuple[str, list[int], list[str], Dict[int, str]]:
    """Join text/title blocks into one string with [BLOCK_N] markers.

    Strips ``【摘要】`` prefix (dropped) and ``【关键词】`` prefix
    (saved for re-add after translation). Inserts ``[REDACTED]``
    markers where OCR values are missing. English-only blocks are
    preserved as-is so the LLM doesn't re-translate them.

    Returns:
        Tuple of (marked_text, block_indices, stripped_prefixes,
        english_overrides). ``stripped_prefixes[i]`` corresponds
        to ``block_indices[i]``. ``english_overrides`` maps
        sequence numbers to original English text for blocks that
        should not be re-translated.
    """
    parts: list[str] = []
    indices: list[int] = []
    prefixes: list[str] = []
    english_overrides: dict[int, str] = {}

    for seq, (block_idx, block) in enumerate(non_empty, start=1):
        text = block.text

        # Strip 【…】 bracket prefixes
        prefix = ""
        kw_match = re.match(r"^【[^】]+】\s*", text)
        if kw_match:
            bracket = kw_match.group(0)
            text = text[kw_match.end():]
            # Keep 【关键词】 for re-add; drop 【摘要】
            if "摘要" not in bracket:
                prefix = bracket.strip()

        # Mark redacted values before translation
        text = mark_redacted_values(text)

        indices.append(block_idx)
        prefixes.append(prefix)

        # If text is already English, preserve it and tell the LLM
        # to pass it through unchanged
        if is_predominantly_english(text):
            english_overrides[seq] = text
            parts.append(f"[BLOCK_{seq}] {text}")
        else:
            parts.append(f"[BLOCK_{seq}] {text}")

    return "\n\n".join(parts), indices, prefixes, english_overrides


def split_by_markers(marked_text: str, n_expected: int) -> list[str]:
    """Split LLM output on [BLOCK_N] markers.

    Returns a list of translated texts, one per block. If markers
    are missing, returns the full text as a single element.
    """
    marker_re = re.compile(r"\[BLOCK_(\d+)\]")
    segments: dict[int, str] = {}

    for m in marker_re.finditer(marked_text):
        seq = int(m.group(1))
        content_start = m.end()
        # Find the next marker (or end of string)
        next_m = marker_re.search(marked_text, content_start)
        content_end = next_m.start() if next_m else len(marked_text)
        content = marked_text[content_start:content_end].strip()
        # Strip leading newlines/separators
        content = content.lstrip("\n").strip()
        if content:
            segments[seq] = content

    if not segments:
        # No markers found — return full text as single element
        return [marked_text.strip()]

    # Reconstruct in order
    result: list[str] = []
    for seq in range(1, n_expected + 1):
        result.append(segments.get(seq, ""))
    return result
