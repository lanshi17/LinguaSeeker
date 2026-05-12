"""Token-budgeted text segmentation for LLM context windows."""
from __future__ import annotations

import re
from typing import List, Optional


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ASCII chars / 4, CJK chars count as 1 each."""
    if not text:
        return 0
    ascii_chars = sum(1 for ch in text if ch.isascii())
    non_ascii_chars = len(text) - ascii_chars
    return int(ascii_chars / 4 + non_ascii_chars)


def _split_paragraph(
    paragraph: str,
    max_tokens: int,
    max_chars: Optional[int] = None,
) -> List[str]:
    """Split one paragraph into chunks that fit within the token budget."""

    def fits(text: str) -> bool:
        if estimate_tokens(text) > max_tokens:
            return False
        if max_chars is not None and len(text) > max_chars:
            return False
        return True

    if fits(paragraph):
        return [paragraph]

    sentences = [s for s in re.split(r"(?<=[。！？.!?])\s+", paragraph.strip()) if s]
    chunks: List[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip() if current else sentence
        if fits(candidate):
            current = candidate
            continue
        if current:
            chunks.append(current)
            current = ""
        if fits(sentence):
            current = sentence
            continue
        # Sentence too long — hard split
        chunk_size = max_chars if max_chars is not None else max_tokens * 4
        chunk_size = max(1, chunk_size)
        start = 0
        while start < len(sentence):
            end = min(len(sentence), start + chunk_size)
            chunks.append(sentence[start:end].strip())
            start = end

    if current:
        chunks.append(current)
    return chunks


def segment_text(
    text: str,
    max_tokens: int = 8192,
    prompt_overhead_tokens: int = 0,
) -> List[str]:
    """Segment ``text`` into chunks that fit within ``max_tokens``.

    Splits on paragraph boundaries first, then on sentences if needed.
    ``prompt_overhead_tokens`` reduces the effective budget per segment.
    """
    effective_max = max(1, max_tokens - prompt_overhead_tokens - 20)
    max_chars = effective_max * 4

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    paragraph_units: List[str] = []
    for para in paragraphs:
        paragraph_units.extend(_split_paragraph(para, effective_max, max_chars))

    segments: List[str] = []
    current = ""
    for unit in paragraph_units:
        candidate = unit if not current else f"{current}\n\n{unit}"
        if estimate_tokens(candidate) <= effective_max and (
            max_chars is None or len(candidate) <= max_chars
        ):
            current = candidate
            continue
        if current:
            segments.append(current)
        current = unit

    if current:
        segments.append(current)
    return segments
