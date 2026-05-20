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

    # Check if output is just echoed prompt (no actual translation)
    prompt_markers = (
        "SYSTEM PROMPT:", "You are a biomedical translation engine",
        "You are a prompt engineering expert", "CRITICAL RULES",
        "TERMINOLOGY STAGE", "TRANSLATE_STAGE",
    )
    first_200 = translated[:200].upper()
    if any(marker.upper() in first_200 for marker in prompt_markers):
        raise ValueError("translation_validation_failed: prompt_echo_only")

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


# Translation table for CJK punctuation -> ASCII equivalents
_CJK_PUNCT_MAP = {
    0x3000: " ",   # full-width space
    0xFF0C: ",",   # Chinese comma
    0x3002: ".",   # Chinese period
    0xFF1B: ";",   # Chinese semicolon
    0xFF1A: ":",   # Chinese colon
    0xFF08: "(",   # Chinese left paren
    0xFF09: ")",   # Chinese right paren
    0xFF1F: "?",   # Chinese question mark
    0xFF01: "!",   # Chinese exclamation
    0x201C: '"',   # left double quotation mark
    0x201D: '"',   # right double quotation mark
    0x2018: "'",   # left single quotation mark
    0x2019: "'",   # right single quotation mark
    0x3010: "[",   # left black lenticular bracket
    0x3011: "]",   # right black lenticular bracket
    0x300A: "<",   # left double angle bracket
    0x300B: ">",   # right double angle bracket
    0x3001: ",",   # Chinese enumeration comma
}
_CJK_PUNCT_TABLE = str.maketrans(_CJK_PUNCT_MAP)


def normalize_cjk_punctuation(text: str) -> str:
    """Replace stray CJK punctuation with ASCII equivalents.

    After translation, some CJK punctuation may remain (full-width spaces,
    Chinese commas, etc.). This normalizes them to ASCII equivalents.
    """
    if not text:
        return text
    return text.translate(_CJK_PUNCT_TABLE)


# Patterns for OCR/parse artifacts that produce empty placeholders
_PLACEHOLDER_PATTERNS = [
    (re.compile(r"\[\s*\]"), ""),           # [ ] → remove
    (re.compile(r"\(year\)"), ""),          # (year) → remove
    (re.compile(r"\(month\)"), ""),         # (month) → remove
    (re.compile(r"\(day\)"), ""),           # (day) → remove
    (re.compile(r"\[year\]"), ""),          # [year] → remove
    (re.compile(r"\[month\]"), ""),         # [month] → remove
    (re.compile(r"\[day\]"), ""),           # [day] → remove
    (re.compile(r"\[age\]"), ""),           # [age] → remove
    (re.compile(r"\[imaging\]"), ""),       # [imaging] → remove
    # LLM-generated "blank" placeholders from OCR-missing values
    (re.compile(r"\bblank\b"), ""),         # standalone "blank" → remove
    (re.compile(r"\[blank\]"), ""),         # [blank] → remove
    # Bare CJK date placeholders that the LLM may pass through untranslated
    (re.compile(r"年\s*月\s*日"), ""),       # 年月日 → remove
    (re.compile(r"\byear[,\s]+month[,\s]+day\b"), ""),  # LLM-translated date placeholder (with/without commas)
    # Empty parentheses from OCR (no content inside)
    (re.compile(r"\(\s*\)"), ""),            # () → remove
]


def normalize_placeholders(text: str) -> str:
    """Normalize OCR/parse placeholder artifacts.

    Removes empty brackets and generic placeholder text that results from
    failed OCR extraction. These pollute downstream NER/variant extraction.
    """
    if not text:
        return text
    for pattern, replacement in _PLACEHOLDER_PATTERNS:
        text = pattern.sub(replacement, text)
    # Clean up orphan prepositions left after placeholder removal ("On ,", "in .")
    text = re.sub(r"\b(?:on|in|at|of)\s*([,.\;])", r"\1", text, flags=re.IGNORECASE)
    # Clean up consecutive orphan prepositions ("on in the Department")
    text = re.sub(r"\b(?:on|in|at)\s+(in|at|of)\b", r"\1", text, flags=re.IGNORECASE)
    # Clean up leading punctuation left after preposition removal (", the patient...")
    text = re.sub(r"^\s*[,;]\s*", "", text)
    # Clean up resulting double-spaces
    text = re.sub(r"  +", " ", text)
    return text.strip()


# Pattern for redundant email colon when address is missing (OCR artifact)
_EMAIL_COLON_RE = re.compile(r"[Ee]mail\s*:\s*:")
_EMAIL_EMPTY_RE = re.compile(r"[Ee]mail\s*:\s*$")
# Trailing orphan colon after author name (no email label)
_TRAILING_ORPHAN_COLON_RE = re.compile(r",\s*:\s*$")


def fix_email_placeholder(text: str) -> str:
    """Fix redundant email colons from OCR-missing addresses.

    Transforms 'Email: :' → 'Email: [unavailable]',
    'Email:' (at end of line) → 'Email: [unavailable]',
    and trailing ', :' (orphan colon without email label) → ''.
    """
    if not text:
        return text
    text = _EMAIL_COLON_RE.sub("Email: [unavailable]", text)
    text = _EMAIL_EMPTY_RE.sub("Email: [unavailable]", text)
    text = _TRAILING_ORPHAN_COLON_RE.sub("", text)
    return text


# OCR truncation patterns common in biomedical CJK documents
# Matches "galactosidase ( , )" or "galactosidase A ( , )" — empty abbreviation
_GALACTOSIDASE_RE = re.compile(
    r"(?<!α-)\bgalactosidase(?:\s+A)?\s*\(\s*,\s*\)",
    re.IGNORECASE,
)
_LINKED_ORPHAN_RE = re.compile(
    r"(?<![A-Za-z])-linked\b",
)


# Also match "α-galactosidase A ( , )" — prefix present but abbreviation missing
_GALACTOSIDASE_FULL_RE = re.compile(
    r"α-galactosidase(?:\s+A)?\s*\(\s*,\s*\)",
    re.IGNORECASE,
)
# Trailing comma inside parenthetical: "(α-Gal A, )" → "(α-Gal A)"
_TRAILING_COMMA_IN_PARENS_RE = re.compile(r",\s*\)")


def fix_ocr_truncations(text: str) -> str:
    """Fix common OCR truncation patterns in biomedical translations.

    Restores terms that upstream OCR commonly truncates:
    - ``galactosidase ( , )`` → ``α-galactosidase A (α-Gal A)``
    - ``α-galactosidase A ( , )`` → ``α-galactosidase A (α-Gal A)``
    - ``-linked`` (missing X prefix) → ``X-linked``
    """
    if not text:
        return text
    text = _GALACTOSIDASE_RE.sub("α-galactosidase A (α-Gal A)", text)
    text = _GALACTOSIDASE_FULL_RE.sub("α-galactosidase A (α-Gal A)", text)
    text = _LINKED_ORPHAN_RE.sub("X-linked", text)
    text = _TRAILING_COMMA_IN_PARENS_RE.sub(")", text)
    return text


# Pattern for [REDACTED] incorrectly inserted inside English words.
# e.g., "Re[REDACTED]ferences" → "References"
_REDACTED_IN_WORD_RE = re.compile(r"(?<=[A-Za-z])\[REDACTED\](?=[A-Za-z])")

# Pattern for [REDACTED] adjacent to common English section headings.
# e.g., "References [REDACTED]" or "[REDACTED] Abstract" — the LLM
# misinterprets headings as containing missing values.
_REDACTED_HEADING_WORDS = (
    "References", "Abstract", "Introduction", "Background",
    "Methods", "Results", "Discussion", "Conclusion",
    "Acknowledgments", "Acknowledgements", "Keywords",
)
_REDACTED_ADJ_HEADING_RE = re.compile(
    r"(?:"
    + "|".join(re.escape(w) for w in _REDACTED_HEADING_WORDS)
    + r")\s*\[REDACTED\]|"
    r"\[REDACTED\]\s*(?:"
    + "|".join(re.escape(w) for w in _REDACTED_HEADING_WORDS)
    + r")",
    re.IGNORECASE,
)


def _strip_adjacent_heading_redacted(match: re.Match) -> str:
    """Strip [REDACTED] from a heading-adjacent match, keeping the heading."""
    text = match.group(0)
    return re.sub(r"\[REDACTED\]\s*", "", text).strip()


def fix_word_boundary_redacted(text: str) -> str:
    """Remove [REDACTED] markers incorrectly inserted around English words.

    The formatter LLM sometimes inserts [REDACTED] mid-word, e.g.
    ``Re[REDACTED]ferences`` instead of ``References``, or adjacent to
    section headings, e.g. ``References [REDACTED]``. This strips such
    markers while preserving legitimate [REDACTED] placeholders.
    """
    if not text:
        return text
    text = _REDACTED_IN_WORD_RE.sub("", text)
    text = _REDACTED_ADJ_HEADING_RE.sub(_strip_adjacent_heading_redacted, text)
    return text


_KEYWORDS_RE = re.compile(
    r"^((?:Key\s*)?Words?\s*:?\s*)(.+)$",
    re.IGNORECASE,
)


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


def normalize_keywords_capitalization(text: str) -> str:
    """Normalize keyword list capitalization to sentence case.

    After the 'Keywords' label, lowercases the first letter of each
    semicolon-separated term unless it looks like an abbreviation
    (all-caps) or proper noun (starts with uppercase followed by
    lowercase but is a known biomedical proper noun).
    """
    if not text:
        return text
    m = _KEYWORDS_RE.match(text.strip())
    if not m:
        return text
    label = m.group(1)
    body = m.group(2)
    terms = [t.strip() for t in body.split(";")]
    normalized: list[str] = []
    for term in terms:
        if not term:
            continue
        # Keep abbreviations (all-caps like GLA, ERT) as-is
        if term[:1].isupper() and len(term) > 1 and term[1:2].isupper():
            normalized.append(term)
        # Keep proper nouns (mixed case like "Fabry", "Parkinson") as-is
        elif any(c.isupper() for c in term[1:]):
            normalized.append(term)
        # Lowercase first letter of common terms
        elif term[0].isupper():
            normalized.append(term[0].lower() + term[1:])
        else:
            normalized.append(term)
    return label + "; ".join(normalized)
