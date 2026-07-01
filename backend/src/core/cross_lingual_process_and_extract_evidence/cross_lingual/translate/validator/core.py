"""Translation quality validation."""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from lingua import Language

from ..language_detector import _CJK_RE, _DETECTOR, _looks_english

_MIN_DOCUMENT_COMPLETENESS_SOURCE_CHARS = 500
_MIN_SEGMENT_COMPLETENESS_SOURCE_CHARS = 220
_MIN_DOCUMENT_TRANSLATED_SOURCE_RATIO = 0.35
_MIN_SEGMENT_TRANSLATED_SOURCE_RATIO = 0.30


def _source_requires_completeness_check(source: str, min_source_chars: int) -> bool:
    """Return whether a source text is long and non-English enough for length coverage checks."""
    if len(source) < min_source_chars:
        return False
    if _looks_english(source):
        return False

    cjk_count = len(_CJK_RE.findall(source))
    if cjk_count / max(len(source), 1) >= 0.05:
        return True

    detected = _DETECTOR.detect_language_of(source[:4000])
    return detected is not None and detected != Language.ENGLISH


def _validate_translation_completeness(
    source: str,
    translated: str,
    *,
    min_source_chars: int,
    min_ratio: float,
    error_prefix: str,
) -> None:
    """Reject long non-English sources that were compressed into a short English summary."""
    if not _source_requires_completeness_check(source, min_source_chars):
        return

    translated_ratio = len(translated) / max(len(source), 1)
    if translated_ratio < min_ratio:
        raise ValueError(
            f"{error_prefix}: incomplete_translation — "
            f"translated/source length ratio {translated_ratio:.0%} "
            f"below {min_ratio:.0%} for {len(source)} source chars"
        )


def validate_translation_output(source_text: str, translated_text: str) -> None:
    """Validate translated output quality.

    Raises ``ValueError`` with a ``translation_validation_failed:`` prefix
    if any check fails.
    """
    source = str(source_text or "").strip()
    translated = str(translated_text or "").strip()

    if not translated:
        raise ValueError("translation_validation_failed: empty")

    # Check if output is just echoed prompt (no actual translation)
    prompt_markers = (
        "SYSTEM PROMPT:",
        "You are a biomedical translation engine",
        "You are a prompt engineering expert",
        "CRITICAL RULES",
        "TERMINOLOGY STAGE",
        "TRANSLATE_STAGE",
    )
    first_200 = translated[:200].upper()
    if any(marker.upper() in first_200 for marker in prompt_markers):
        raise ValueError("translation_validation_failed: prompt_echo_only")

    # Check CJK ratio — if >10% CJK, likely not translated
    cjk_count = len(_CJK_RE.findall(translated))
    if cjk_count and len(translated) > 0 and cjk_count / len(translated) > 0.10:
        raise ValueError("translation_validation_failed: non_english_output")

    # Check if translation is essentially unchanged from source.
    # Skip for short texts (<100 chars) where shared technical terms
    # (gene names, mutation notation) inflate the similarity ratio.
    # Also skip when the source is already English — translating an English
    # document produces similar text by design.
    if source and len(source) >= 100:
        ratio = SequenceMatcher(None, source.lower(), translated.lower()).ratio()
        if ratio >= 0.85 and not _looks_english(source):
            raise ValueError("translation_validation_failed: unchanged")

    _validate_translation_completeness(
        source,
        translated,
        min_source_chars=_MIN_DOCUMENT_COMPLETENESS_SOURCE_CHARS,
        min_ratio=_MIN_DOCUMENT_TRANSLATED_SOURCE_RATIO,
        error_prefix="translation_validation_failed",
    )

    # Check detected language of output.
    # The lingua detector misclassifies text heavy in gene mutation notation
    # (p.R106W, c.C316T, etc.) as Latin/French.  Fall back to word-frequency
    # heuristic when the detector disagrees.
    detected = _DETECTOR.detect_language_of(translated[:4000])
    if detected is not None and detected != Language.ENGLISH:
        if not _looks_english(translated):
            raise ValueError("translation_validation_failed: non_english_output")


def summarize_validation_error(exc: Exception) -> str:
    """Extract a concise error summary from a validation exception."""
    message = str(exc or "").strip()
    if message.startswith("translation_validation_failed:"):
        return message
    return f"translation_validation_failed: {message or 'unknown'}"


def validate_segment(source: str, translated: str) -> None:
    """Validate a single translated segment.

    Lighter than ``validate_translation_output`` — checks for empty output,
    source-language contamination, and size anomalies. Used for per-segment
    retry decisions during translation.

    Raises:
        ValueError: If the segment fails validation.
    """
    translated = str(translated or "").strip()
    if not translated:
        raise ValueError("segment_validation_failed: empty")

    # Check CJK ratio — >15% CJK in a segment means likely not fully translated
    cjk_count = len(_CJK_RE.findall(translated))
    total = len(translated) or 1
    if cjk_count / total > 0.15:
        raise ValueError("segment_validation_failed: source_language_content")

    # Check if translation is essentially unchanged from source
    # Skip for English-only source (author names, affiliations) — LLM correctly
    # leaves these unchanged, but validation would flag as false positive.
    source = str(source or "").strip()
    if source:
        source_cjk = len(_CJK_RE.findall(source))
        source_total = len(source) or 1
        if source_cjk / source_total >= 0.05:
            ratio = SequenceMatcher(None, source.lower(), translated.lower()).ratio()
            if ratio >= 0.90:
                raise ValueError("segment_validation_failed: unchanged")

    # Check for LLM repetition — translated should not be >3x source
    if source and len(translated) > len(source) * 3:
        headings = re.findall(r"^#{1,6}\s+.+", translated, re.MULTILINE)
        if len(set(headings)) < len(headings):
            raise ValueError("segment_validation_failed: repetition_loop")

    _validate_translation_completeness(
        source,
        translated,
        min_source_chars=_MIN_SEGMENT_COMPLETENESS_SOURCE_CHARS,
        min_ratio=_MIN_SEGMENT_TRANSLATED_SOURCE_RATIO,
        error_prefix="segment_validation_failed",
    )


_IMAGE_REF_RE = re.compile(r"!\[.*?\]\((.*?)\)")


def validate_image_references_preserved(source: str, translated: str) -> None:
    """Validate that all image references from source are preserved in translation.

    Args:
        source: Original markdown text.
        translated: Translated markdown text.

    Raises:
        ValueError: If image references are missing from translation.
    """
    source_images = set(_IMAGE_REF_RE.findall(source))
    translated_images = set(_IMAGE_REF_RE.findall(translated))

    missing = source_images - translated_images
    if missing:
        raise ValueError(
            f"Image references missing from translation: {missing}. "
            f"Source has {len(source_images)} images, translated has {len(translated_images)}."
        )
