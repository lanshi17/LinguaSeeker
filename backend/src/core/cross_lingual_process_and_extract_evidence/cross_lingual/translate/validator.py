"""Translation quality validation and assessment."""
from __future__ import annotations

import re
from difflib import SequenceMatcher

from lingua import Language
from loguru import logger

from .language_detector import _CJK_RE, _DETECTOR


def validate_translation_output(source_text: str, translated_text: str) -> None:
    """Validate translated output quality.

    Raises ``ValueError`` with a ``translation_validation_failed:`` prefix
    if any check fails.
    """
    source = str(source_text or "").strip()
    translated = str(translated_text or "").strip()

    if not translated:
        raise ValueError("translation_validation_failed: empty")

    # Check CJK ratio — if >10% CJK, likely not translated
    cjk_count = len(_CJK_RE.findall(translated))
    if cjk_count and len(translated) > 0 and cjk_count / len(translated) > 0.10:
        raise ValueError("translation_validation_failed: non_english_output")

    # Check if translation is essentially unchanged from source
    ratio = SequenceMatcher(None, source.lower(), translated.lower()).ratio()
    if source and ratio >= 0.85:
        raise ValueError("translation_validation_failed: unchanged")

    # Check detected language of output
    detected = _DETECTOR.detect_language_of(translated[:4000])
    if detected is not None and detected != Language.ENGLISH:
        raise ValueError("translation_validation_failed: non_english_output")


def summarize_validation_error(exc: Exception) -> str:
    """Extract a concise error summary from a validation exception."""
    message = str(exc or "").strip()
    if message.startswith("translation_validation_failed:"):
        return message
    return f"translation_validation_failed: {message or 'unknown'}"


def strip_source_contamination(translated: str, source_language: str = "unknown") -> str:
    """Strip source-language text from LLM translation output.

    Some translation models return both the translation and the original text,
    either appended after the translation or prepended before it. This function
    detects both patterns and returns only the translated portion.

    Args:
        translated: The LLM output that may contain source text.
        source_language: The source language code (e.g., "ja", "zh", "ru").

    Returns:
        The translated text with source-language contamination removed.
    """
    if not translated or source_language == "en":
        return translated

    paragraphs = re.split(r"\n\s*\n", translated)

    # Pass 1: Strip leading source-language paragraphs
    # Skip paragraphs at the start that are predominantly CJK
    start_idx = 0
    for idx, para in enumerate(paragraphs):
        stripped = para.strip()
        if not stripped:
            continue
        cjk_count = len(_CJK_RE.findall(stripped))
        total = len(stripped) or 1
        cjk_ratio = cjk_count / total
        # A paragraph is "English" if <10% CJK characters
        if cjk_ratio < 0.10:
            start_idx = idx
            break
        # If >= 10% CJK, treat as source-language — skip it
        logger.debug(
            "Skipping leading source paragraph (cjk_ratio={:.2f}): {}...",
            cjk_ratio, stripped[:60],
        )
    else:
        # All paragraphs are source-language — nothing to strip
        start_idx = len(paragraphs)

    if start_idx > 0:
        paragraphs = paragraphs[start_idx:]
        logger.info("Stripped {} leading source paragraphs", start_idx)

    # Pass 2: Strip trailing source-language paragraphs (original behavior)
    clean_parts: list[str] = []
    contamination_started = False

    for para in paragraphs:
        stripped = para.strip()
        if not stripped:
            clean_parts.append(para)
            continue

        # Calculate CJK character ratio for this paragraph
        cjk_count = len(_CJK_RE.findall(stripped))
        total = len(stripped) or 1
        cjk_ratio = cjk_count / total

        # If a paragraph is >40% CJK and we already have substantial English
        # content, treat it as source-language contamination
        if cjk_ratio > 0.40 and len(clean_parts) >= 2:
            # Check if we already have enough English content before this
            english_chars = sum(
                len(p) for p in clean_parts
                if len(_CJK_RE.findall(p)) / (len(p) or 1) < 0.20
            )
            if english_chars > 200:
                contamination_started = True
                logger.debug(
                    "Stripping trailing source contamination at paragraph (cjk_ratio={:.2f}): {}...",
                    cjk_ratio, stripped[:60],
                )
                break

        clean_parts.append(para)

    if not contamination_started and start_idx == 0:
        return translated

    result = "\n\n".join(clean_parts).strip()
    if len(result) < 100:
        # Safety: if almost nothing remains, likely a false positive
        logger.warning("Contamination strip left <100 chars, keeping original")
        return translated

    logger.info(
        "Stripped source contamination: {} -> {} chars",
        len(translated), len(result),
    )
    return result


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

    # Check CJK ratio — >30% CJK in a segment means likely not translated
    cjk_count = len(_CJK_RE.findall(translated))
    total = len(translated) or 1
    if cjk_count / total > 0.30:
        raise ValueError("segment_validation_failed: source_language_content")

    # Check if translation is essentially unchanged from source
    source = str(source or "").strip()
    if source:
        ratio = SequenceMatcher(None, source.lower(), translated.lower()).ratio()
        if ratio >= 0.90:
            raise ValueError("segment_validation_failed: unchanged")

    # Check for LLM repetition — translated should not be >3x source
    if source and len(translated) > len(source) * 3:
        headings = re.findall(r"^#{1,6}\s+.+", translated, re.MULTILINE)
        if len(set(headings)) < len(headings):
            raise ValueError("segment_validation_failed: repetition_loop")


def validate_image_references_preserved(source: str, translated: str) -> None:
    """Validate that all image references from source are preserved in translation.

    Args:
        source: Original markdown text.
        translated: Translated markdown text.

    Raises:
        ValueError: If image references are missing from translation.
    """
    image_pattern = re.compile(r"!\[.*?\]\((.*?)\)")
    source_images = set(image_pattern.findall(source))
    translated_images = set(image_pattern.findall(translated))

    missing = source_images - translated_images
    if missing:
        raise ValueError(
            f"Image references missing from translation: {missing}. "
            f"Source has {len(source_images)} images, translated has {len(translated_images)}."
        )
