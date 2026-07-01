"""Semantic and fallback span alignment for original-English translations."""
from __future__ import annotations

import re
import json
from dataclasses import dataclass
from typing import Any, Literal, Sequence

from loguru import logger

from ...contracts import TranslationAlignmentChunk, TranslationSpanPair
from .providers import invoke_json_with_retry

_TOKEN_RE = re.compile(
    r"[cp]\.\d+[A-Za-z0-9_>.-]*"
    r"|[A-Z][A-Z0-9]{1,}(?:[-_][A-Z0-9]+)*"
    r"|[A-Za-z]+(?:[-'][A-Za-z]+)*"
    r"|\d+(?:\.\d+)?"
    r"|[\u4e00-\u9fff]{1,6}",
    re.IGNORECASE,
)
_MIN_SEMANTIC_ALIGNMENT_CHARS = 8


@dataclass(frozen=True)
class RawAlignmentPair:
    """Raw copied span texts returned by semantic alignment generation."""

    original_text: str
    english_text: str
    confidence: float = 0.0


@dataclass(frozen=True)
class _Token:
    text: str
    start: int
    end: int


def validate_span_pairs(
    chunk: TranslationAlignmentChunk,
    raw_pairs: Sequence[RawAlignmentPair],
    *,
    method: Literal["semantic_llm", "deterministic_token"] = "semantic_llm",
) -> list[TranslationSpanPair]:
    """Validate raw copied span pairs and convert them to full-document offsets."""
    accepted: list[TranslationSpanPair] = []
    original_cursor = 0
    english_cursor = 0

    for raw in raw_pairs:
        original_text = raw.original_text.strip()
        english_text = raw.english_text.strip()
        if not original_text or not english_text:
            continue

        original_local_start = chunk.original_text.find(original_text, original_cursor)
        english_local_start = chunk.english_text.find(english_text, english_cursor)
        if original_local_start < 0:
            original_local_start = chunk.original_text.find(original_text)
        if english_local_start < 0:
            english_local_start = chunk.english_text.find(english_text)
        if original_local_start < 0 or english_local_start < 0:
            continue

        original_local_end = original_local_start + len(original_text)
        english_local_end = english_local_start + len(english_text)
        original_start = chunk.original_start_offset + original_local_start
        original_end = chunk.original_start_offset + original_local_end
        english_start = chunk.english_start_offset + english_local_start
        english_end = chunk.english_start_offset + english_local_end
        if not _range_within_chunk(chunk, original_start, original_end, english_start, english_end):
            continue
        if _overlaps_existing(accepted, original_start, original_end, english_start, english_end):
            continue

        pair_index = len(accepted) + 1
        accepted.append(TranslationSpanPair(
            pair_id=f"{chunk.chunk_id}-p_{pair_index:04d}",
            original_text=original_text,
            english_text=english_text,
            original_start_offset=original_start,
            original_end_offset=original_end,
            english_start_offset=english_start,
            english_end_offset=english_end,
            confidence=raw.confidence,
            method=method,
        ))
        original_cursor = original_local_end
        english_cursor = english_local_end

    return accepted


async def generate_chunk_span_pairs(
    json_llm: Any,
    chunk: TranslationAlignmentChunk,
    source_language: str,
    stage: str,
) -> list[TranslationSpanPair]:
    """Generate semantic span pairs for a chunk, falling back deterministically."""
    if (
        len(chunk.original_text.strip()) < _MIN_SEMANTIC_ALIGNMENT_CHARS
        or len(chunk.english_text.strip()) < _MIN_SEMANTIC_ALIGNMENT_CHARS
    ):
        return build_fallback_span_pairs(chunk)

    prompt = _build_alignment_prompt(chunk, source_language)
    try:
        raw = await invoke_json_with_retry(json_llm, prompt, stage)
        payload = json.loads(raw)
        raw_pairs = _parse_raw_pairs(payload)
        semantic_pairs = validate_span_pairs(chunk, raw_pairs, method="semantic_llm")
        if semantic_pairs:
            return semantic_pairs
        logger.warning("Semantic alignment returned no valid pairs for {}", chunk.chunk_id)
    except (json.JSONDecodeError, TypeError, ValueError, RuntimeError) as exc:
        logger.warning("Semantic alignment failed for {}: {}", chunk.chunk_id, exc)

    return build_fallback_span_pairs(chunk)


def build_fallback_span_pairs(chunk: TranslationAlignmentChunk) -> list[TranslationSpanPair]:
    """Build deterministic monotonic token-level span pairs for a chunk."""
    source_tokens = _tokenize(chunk.original_text)
    english_tokens = _tokenize(chunk.english_text)
    if not source_tokens or not english_tokens:
        return []

    pairs: list[TranslationSpanPair] = []
    english_cursor = 0
    for source_index, source_token in enumerate(source_tokens):
        english_index = _select_fallback_english_index(
            source_token, english_tokens, english_cursor, source_index, len(source_tokens),
        )
        if english_index is None:
            break
        english_token = english_tokens[english_index]
        english_cursor = english_index + 1

        pair_index = len(pairs) + 1
        pairs.append(TranslationSpanPair(
            pair_id=f"{chunk.chunk_id}-fb_{pair_index:04d}",
            original_text=source_token.text,
            english_text=english_token.text,
            original_start_offset=chunk.original_start_offset + source_token.start,
            original_end_offset=chunk.original_start_offset + source_token.end,
            english_start_offset=chunk.english_start_offset + english_token.start,
            english_end_offset=chunk.english_start_offset + english_token.end,
            confidence=0.2,
            method="deterministic_token",
        ))

    return pairs


def _build_alignment_prompt(chunk: TranslationAlignmentChunk, source_language: str) -> str:
    """Build the JSON-only semantic alignment prompt."""
    payload = {
        "chunk_id": chunk.chunk_id,
        "source_language": source_language,
        "original_text": chunk.original_text,
        "english_text": chunk.english_text,
    }
    return (
        "Align clinically meaningful source-language words or phrases to their English translation.\n"
        "Return ONLY a JSON object with key \"pairs\" whose value is an array of objects.\n"
        "Each object must contain exact copied substrings: original_text, english_text, confidence.\n"
        "Prefer biomedical terms, gene symbols, variants, diseases, numbers, section labels, and key verbs.\n"
        "Do not invent text. Preserve monotonic reading order when possible.\n\n"
        f"Input:\n{json.dumps(payload, ensure_ascii=False)}"
    )


def _parse_raw_pairs(payload: Any) -> list[RawAlignmentPair]:
    """Parse raw provider JSON into typed raw pairs."""
    if not isinstance(payload, dict):
        return []
    raw_items = payload.get("pairs")
    if not isinstance(raw_items, list):
        return []

    pairs: list[RawAlignmentPair] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        original_text = item.get("original_text")
        english_text = item.get("english_text")
        if not isinstance(original_text, str) or not isinstance(english_text, str):
            continue
        confidence = item.get("confidence", 0.0)
        if not isinstance(confidence, (int, float)):
            confidence = 0.0
        pairs.append(RawAlignmentPair(
            original_text=original_text,
            english_text=english_text,
            confidence=max(0.0, min(float(confidence), 1.0)),
        ))
    return pairs


def _range_within_chunk(
    chunk: TranslationAlignmentChunk,
    original_start: int,
    original_end: int,
    english_start: int,
    english_end: int,
) -> bool:
    return (
        chunk.original_start_offset <= original_start < original_end <= chunk.original_end_offset
        and chunk.english_start_offset <= english_start < english_end <= chunk.english_end_offset
    )


def _overlaps_existing(
    pairs: Sequence[TranslationSpanPair],
    original_start: int,
    original_end: int,
    english_start: int,
    english_end: int,
) -> bool:
    for pair in pairs:
        original_overlaps = original_start < pair.original_end_offset and original_end > pair.original_start_offset
        english_overlaps = english_start < pair.english_end_offset and english_end > pair.english_start_offset
        if original_overlaps or english_overlaps:
            return True
    return False


def _tokenize(text: str) -> list[_Token]:
    return [_Token(match.group(0), match.start(), match.end()) for match in _TOKEN_RE.finditer(text)]


def _select_fallback_english_index(
    source_token: _Token,
    english_tokens: Sequence[_Token],
    english_cursor: int,
    source_index: int,
    source_count: int,
) -> int | None:
    source_norm = _normalize_token(source_token.text)
    for english_index in range(english_cursor, len(english_tokens)):
        if _normalize_token(english_tokens[english_index].text) == source_norm:
            return english_index

    if english_cursor >= len(english_tokens):
        return None
    if source_count <= 1:
        return english_cursor
    proportional = round(source_index * (len(english_tokens) - 1) / max(source_count - 1, 1))
    return max(english_cursor, min(proportional, len(english_tokens) - 1))


def _normalize_token(token: str) -> str:
    return token.casefold().strip()
