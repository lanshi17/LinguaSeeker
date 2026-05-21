"""Redacted value detection and marking for OCR-processed documents."""
from __future__ import annotations

import re


# Minimal patterns for obvious structural artifacts (empty brackets only).
# Complex missing-value detection is handled by LLM in formatter stage.
_REDACTED_PATTERNS = [
    # Empty brackets: "（ ）" → "（[REDACTED]）"
    (re.compile(r"（\s+）"), "（[REDACTED]）"),
    (re.compile(r"\(\s+\)"), "([REDACTED])"),
]

# Generic CJK-gap detection: catches whitespace between CJK characters
# followed by common value indicators (units, counters, punctuation).
# This is a safety net for values the LLM formatter may have missed.
_CJK_GAP_PATTERNS = [
    # CJK + space + counter word: "纳入了 例" → "纳入了 [REDACTED] 例"
    (re.compile(r"([一-鿿])\s+([例个次名岁天月年期])"), r"\1 [REDACTED] \2"),
    # CJK + space + punctuation: "尿蛋白 ，" → "尿蛋白 [REDACTED]，"
    (re.compile(r"([一-鿿])\s+([，。；：、])"), r"\1 [REDACTED]\2"),
    # CJK + space + CJK (only when both sides are value-related characters)
    # e.g., "心脏 超" but not "患者 男性" (intentional spacing)
    (re.compile(r"([一-鿿])\s+([一-鿿])(?=[，。；：、\s])"), r"\1 [REDACTED] \2"),
]


def mark_redacted_values(text: str) -> str:
    """Insert [REDACTED] markers where OCR values are missing.

    Uses a two-pass approach:
    1. LLM formatter (primary) - handles complex patterns in get_format_prompt
    2. Regex safety net (this function) - catches remaining CJK gaps

    In Chinese medical documents, redacted/sensitive values appear as
    bare spaces between characters. The regex patterns here are intentionally
    generic to catch any gaps the LLM formatter missed.
    """
    if not text:
        return text
    # Pass 1: structural artifacts (empty brackets)
    for pattern, replacement in _REDACTED_PATTERNS:
        text = pattern.sub(replacement, text)
    # Pass 2: generic CJK-gap safety net
    for pattern, replacement in _CJK_GAP_PATTERNS:
        text = pattern.sub(replacement, text)
    # Clean up double markers
    text = re.sub(r"\[REDACTED\]\s*\[REDACTED\]", "[REDACTED]", text)
    return text
