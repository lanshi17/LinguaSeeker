"""Translation quality validation and assessment."""
from __future__ import annotations

import re
from difflib import SequenceMatcher

from lingua import Language

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
    """Strip source-language text appended by the LLM after the translation.

    Some translation models return both the translation and the original text.
    This function detects the boundary and returns only the translated portion.

    Args:
        translated: The LLM output that may contain appended source text.
        source_language: The source language code (e.g., "ja", "zh", "ru").

    Returns:
        The translated text with source-language contamination removed.
    """
    if not translated or source_language == "en":
        return translated

    paragraphs = re.split(r"\n\s*\n", translated)
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
                    "Stripping source contamination at paragraph (cjk_ratio={:.2f}): {}...",
                    cjk_ratio, stripped[:60],
                )
                break

        clean_parts.append(para)

    if not contamination_started:
        return translated

    result = "\n\n".join(clean_parts).strip()
    if len(result) < len(translated) * 0.3:
        # Safety: if we removed >70%, the whole thing might be the source text
        # Return original and let validation catch it
        logger.warning("Contamination strip removed >70% of text, keeping original")
        return translated

    logger.info(
        "Stripped source contamination: {} -> {} chars",
        len(translated), len(result),
    )
    return result


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
