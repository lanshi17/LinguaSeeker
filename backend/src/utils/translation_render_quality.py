"""Helpers for detecting stale translated render payloads."""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from src.utils.text_normalize import block_text_from_dict

_CJK_RE = re.compile(r"[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]")
_WHITESPACE_RE = re.compile(r"\s+")
_CJK_SOURCE_LANGS = frozenset({"zh", "ja", "ko"})
_UNKNOWN_LANGS = frozenset({"", "unknown", "und", "none", "null"})
_SOURCE_CJK_RATIO = 0.05
_UNTRANSLATED_CJK_RATIO = 0.10
_SAME_TEXT_MIN_CHARS = 80
_SAME_TEXT_SAMPLE_CHARS = 12_000
_SAME_TEXT_RATIO = 0.97


def _normalize_language_code(value: str | None) -> str:
    """Normalize a source-language value to the short code used in the pipeline."""
    aliases = {
        "chinese": "zh",
        "japanese": "ja",
        "korean": "ko",
        "zh-cn": "zh",
        "zh-tw": "zh",
        "zho": "zh",
        "jpn": "ja",
        "kor": "ko",
        "eng": "en",
        "english": "en",
    }
    text = str(value or "").strip().casefold().replace("_", "-")
    return aliases.get(text, text)


def _cjk_ratio(text: str | None) -> float:
    """Return CJK script ratio in text."""
    value = str(text or "")
    if not value:
        return 0.0
    return len(_CJK_RE.findall(value)) / len(value)


def _compact_for_similarity(text: str | None) -> str:
    """Compact text enough for cheap stale-cache comparison."""
    return _WHITESPACE_RE.sub("", str(text or "").casefold())[:_SAME_TEXT_SAMPLE_CHARS]


def _source_requires_english_translation(source_language: str | None, original_text: str | None) -> bool:
    """Return whether the render payload should be English, not copied source text."""
    language = _normalize_language_code(source_language)
    if language not in _UNKNOWN_LANGS and language != "en":
        return True
    return _cjk_ratio(original_text) >= _SOURCE_CJK_RATIO


def _looks_same_as_original(original_text: str | None, translated_text: str | None) -> bool:
    """Return whether translated text is effectively a copy of original text."""
    original = _compact_for_similarity(original_text)
    translated = _compact_for_similarity(translated_text)
    if not original or not translated:
        return False
    if min(len(original), len(translated)) < _SAME_TEXT_MIN_CHARS:
        return original == translated
    length_ratio = min(len(original), len(translated)) / max(len(original), len(translated))
    if length_ratio < 0.90:
        return False
    return SequenceMatcher(None, original, translated).ratio() >= _SAME_TEXT_RATIO


def is_likely_untranslated_render_payload(
    *,
    source_language: str | None,
    original_text: str | None,
    translated_text: str | None,
) -> bool:
    """Return whether a stored translated document is clearly still source text."""
    if not translated_text or not translated_text.strip():
        return False
    if not _source_requires_english_translation(source_language, original_text):
        return False

    language = _normalize_language_code(source_language)
    source_is_cjk = language in _CJK_SOURCE_LANGS or _cjk_ratio(original_text) >= _SOURCE_CJK_RATIO
    if source_is_cjk and _cjk_ratio(translated_text) > _UNTRANSLATED_CJK_RATIO:
        return True
    return _looks_same_as_original(original_text, translated_text)


def _blocks_to_text(blocks: list[dict] | None) -> str | None:
    """Concatenate readable text from serialized content blocks."""
    parts: list[str] = []
    for block in blocks or []:
        if not isinstance(block, dict):
            continue
        text = block_text_from_dict(block)
        if text:
            parts.append(text)
    text = "\n\n".join(parts).strip()
    return text or None


def is_likely_untranslated_render_blocks(
    *,
    source_language: str | None,
    original_blocks: list[dict] | None,
    translated_blocks: list[dict] | None,
) -> bool:
    """Return whether stored translated blocks are clearly still source text."""
    return is_likely_untranslated_render_payload(
        source_language=source_language,
        original_text=_blocks_to_text(original_blocks),
        translated_text=_blocks_to_text(translated_blocks),
    )
