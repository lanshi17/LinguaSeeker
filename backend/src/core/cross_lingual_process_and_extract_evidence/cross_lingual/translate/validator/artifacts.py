"""Artifact stripping for LLM translation output."""
from __future__ import annotations

import re

from loguru import logger

from ..language_detector import _CJK_RE


_ARTIFACT_PATTERNS = [
    r"^SYSTEM\s+PROMPT",
    r"^#{0,3}\s*CRITICAL\s+RULES",
    r"^CRITICAL\s+RULES",
    r"^TERMINOLOGY\s+MAP",
    r"^TRANSLATE_STAGE",
    r"^TERMINOLOGY_STAGE",
    r"^MARKDOWN\s+SEGMENT",
    r"^SOURCE\s+DOCUMENT",
    r"^\[TRANSLATION\]",
    r"^\[TERMINOLOGY\]",
    r"^\[TRANSLATE\s+THIS\s+SEGMENT\]",
    r"^\[PRECEDING\s+CONTEXT",
    r"^\[FOLLOWING\s+CONTEXT",
    r"^\[SYSTEM\s+INSTRUCTIONS",
    r"^\[IMPORTANT:",
    r"^You are a faithful biomedical translation engine",
    r"^You are a bilingual biomedical terminology",
    r"^You are a biomedical translation engine",
    r"^Translate the following markdown segment",
    r"^Preserve ALL markdown structure",
    r"^# Terminology Stage",
    r"^# Bilingual Term Pairs",
    r"^## Bilingual Term Pairs",
    r"^## Preservation Rules",
    r"^\d+\.\s+\*\*Preservation Rules\*\*",
    r"^\*\*Preservation Rules\*\*",
    r"^These bilingual term pairs",
    r"^Bilingual Terminology Map",
]

# Inline patterns to strip from any line within a block (not just first line)
_INLINE_ARTIFACT_PATTERNS = [
    r"\[SYSTEM\s+INSTRUCTIONS[^\]]*\]",
    r"\[IMPORTANT:[^\]]*\]",
    r"\[TRANSLATION\]",
    r"«BLK»",
]
_INLINE_ARTIFACT_RE = re.compile(
    "|".join(f"(?:{p})" for p in _INLINE_ARTIFACT_PATTERNS),
    re.IGNORECASE,
)
_ARTIFACT_RE = re.compile(
    "|".join(f"(?:{p})" for p in _ARTIFACT_PATTERNS),
    re.IGNORECASE | re.MULTILINE,
)


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


def strip_prompt_artifacts(text: str) -> str:
    """Remove prompt instructions that the LLM echoed back in its output.

    Translation models sometimes parrot back the prompt's instruction blocks
    (CRITICAL RULES, TERMINOLOGY MAP, stage headers, etc.) after the actual
    translation. This function strips those artifacts.
    """
    if not text:
        return text

    paragraphs = re.split(r"\n\s*\n", text)
    clean: list[str] = []
    for para in paragraphs:
        first_line = para.strip().split("\n", 1)[0].strip()
        if _ARTIFACT_RE.match(first_line):
            logger.debug("Stripping prompt artifact: {}...", first_line[:60])
            break
        clean.append(para)

    result = "\n\n".join(clean).strip()
    if not result and text.strip():
        # Safety: if we stripped everything, keep original
        logger.warning("Prompt artifact strip removed all content, keeping original")
        return text
    return result


def strip_inline_artifacts(text: str) -> str:
    """Remove inline prompt injection markers and block delimiters from text.

    Strips patterns like [SYSTEM INSTRUCTIONS...], [IMPORTANT:...], and «BLK»
    that the LLM echoed back within translated paragraphs.
    """
    if not text:
        return text
    result = _INLINE_ARTIFACT_RE.sub("", text)
    # Clean up resulting double-spaces or empty lines
    result = re.sub(r"[ \t]{2,}", " ", result)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


# Pattern for the [TRANSLATE THIS SEGMENT] marker that separates prompt echo
# from actual translation output.
_TRANSLATE_THIS_RE = re.compile(
    r"\[TRANSLATE\s+THIS\s+SEGMENT\]",
    re.IGNORECASE,
)

# Broader set of prompt markers that indicate the start of echoed prompt content.
# Used to find the LAST such marker and keep only content after it.
_PROMPT_ECHO_MARKERS_RE = re.compile(
    r"(?:"
    r"\[SYSTEM\s+INSTRUCTIONS"
    r"|\*\*SYSTEM\s+PROMPT"
    r"|\[TERMINOLOGY\]"
    r"|\[PRECEDING\s+CONTEXT"
    r"|\[FOLLOWING\s+CONTEXT"
    r"|\[TRANSLATE\s+THIS\s+SEGMENT\]"
    r")",
    re.IGNORECASE,
)


def strip_prompt_echo(text: str) -> str:
    """Strip LLM prompt echo by finding the last prompt marker.

    When the LLM echoes back the full prompt (system instructions, terminology,
    context markers) before the actual translation, this function finds the
    last prompt marker and returns only the content after it.
    """
    if not text:
        return text

    # Find the last prompt marker — everything before it is echo
    last_match = None
    for m in _PROMPT_ECHO_MARKERS_RE.finditer(text):
        last_match = m

    if last_match:
        translation = text[last_match.end():].strip()
        # Strip leading markers like ":" or "**" after the marker
        translation = re.sub(r"^[:\s*]+", "", translation).strip()
        if translation and len(translation) > 10:
            logger.debug(
                "Stripped prompt echo ({} -> {} chars)",
                len(text), len(translation),
            )
            return translation

    # Fallback: try [TRANSLATE THIS SEGMENT] specifically
    match = _TRANSLATE_THIS_RE.search(text)
    if match:
        translation = text[match.end():].strip()
        if translation:
            logger.debug(
                "Stripped prompt echo via fallback ({} -> {} chars)",
                len(text), len(translation),
            )
            return translation

    return text


_TERM_ECHO_RE = re.compile(r"^.+:\s+.+(?:\n.+:\s+.+){2,}")


def _is_terminology_echo(text: str) -> bool:
    """Detect when the LLM echoed back the terminology map without translating.

    Returns True if the text looks like 3+ consecutive ``source: target`` pairs,
    which is the terminology map format — not a translation.
    """
    stripped = text.strip()
    if not stripped:
        return False
    # Check for 3+ consecutive "source: target" lines
    if _TERM_ECHO_RE.match(stripped):
        # Verify most lines match the pattern
        lines = stripped.splitlines()
        pair_count = sum(1 for ln in lines if re.match(r"^.+:\s+.+$", ln.strip()))
        if pair_count >= 3 and pair_count >= len(lines) * 0.5:
            return True
    return False
