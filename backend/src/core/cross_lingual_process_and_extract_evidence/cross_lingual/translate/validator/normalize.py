"""Text normalization and OCR artifact repair."""

from __future__ import annotations

import re


# Translation table for CJK punctuation -> ASCII equivalents
_CJK_PUNCT_MAP = {
    0x3000: " ",  # full-width space
    0xFF0C: ",",  # Chinese comma
    0x3002: ".",  # Chinese period
    0xFF1B: ";",  # Chinese semicolon
    0xFF1A: ":",  # Chinese colon
    0xFF08: "(",  # Chinese left paren
    0xFF09: ")",  # Chinese right paren
    0xFF1F: "?",  # Chinese question mark
    0xFF01: "!",  # Chinese exclamation
    0x201C: '"',  # left double quotation mark
    0x201D: '"',  # right double quotation mark
    0x2018: "'",  # left single quotation mark
    0x2019: "'",  # right single quotation mark
    0x3010: "[",  # left black lenticular bracket
    0x3011: "]",  # right black lenticular bracket
    0x300A: "<",  # left double angle bracket
    0x300B: ">",  # right double angle bracket
    0x3001: ",",  # Chinese enumeration comma
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
    (re.compile(r"\[\s*\]"), ""),  # [ ] → remove
    (re.compile(r"\(year\)"), ""),  # (year) → remove
    (re.compile(r"\(month\)"), ""),  # (month) → remove
    (re.compile(r"\(day\)"), ""),  # (day) → remove
    (re.compile(r"\[year\]"), ""),  # [year] → remove
    (re.compile(r"\[month\]"), ""),  # [month] → remove
    (re.compile(r"\[day\]"), ""),  # [day] → remove
    (re.compile(r"\[age\]"), ""),  # [age] → remove
    (re.compile(r"\[imaging\]"), ""),  # [imaging] → remove
    # LLM-generated "blank" placeholders from OCR-missing values
    (re.compile(r"\bblank\b"), ""),  # standalone "blank" → remove
    (re.compile(r"\[blank\]"), ""),  # [blank] → remove
    # Bare CJK date placeholders that the LLM may pass through untranslated
    (re.compile(r"年\s*月\s*日"), ""),  # 年月日 → remove
    (re.compile(r"\byear[,\s]+month[,\s]+day\b"), ""),  # LLM-translated date placeholder (with/without commas)
    # Empty parentheses from OCR (no content inside)
    (re.compile(r"\(\s*\)"), ""),  # () → remove
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


# Pattern for [REDACTED] incorrectly inserted inside or adjacent to English words.
# Matches when [REDACTED] is between letters (mid-word) OR after a space before
# a letter (name-internal insertion like "Takayuki [REDACTED]okia").
# e.g., "Re[REDACTED]ferences" → "References"
# e.g., "Takayuki [REDACTED]okia" → "Takayuki Motoki" (after strip)
_REDACTED_IN_WORD_RE = re.compile(
    r"(?<=[A-Za-z])\[REDACTED\](?=[A-Za-z])"  # mid-word: Re[REDACTED]ferences
    r"|\[REDACTED\](?=[a-z])"  # space-before-lowercase: [REDACTED]okia
)

# Pattern for [REDACTED] adjacent to common English section headings.
# e.g., "References [REDACTED]" or "[REDACTED] Abstract" — the LLM
# misinterprets headings as containing missing values.
_REDACTED_HEADING_WORDS = (
    "References",
    "Abstract",
    "Introduction",
    "Background",
    "Methods",
    "Results",
    "Discussion",
    "Conclusion",
    "Acknowledgments",
    "Acknowledgements",
    "Keywords",
)
_REDACTED_ADJ_HEADING_RE = re.compile(
    r"(?:" + "|".join(re.escape(w) for w in _REDACTED_HEADING_WORDS) + r")\s*\[REDACTED\]|"
    r"\[REDACTED\]\s*(?:" + "|".join(re.escape(w) for w in _REDACTED_HEADING_WORDS) + r")",
    re.IGNORECASE,
)


def _strip_adjacent_heading_redacted(match: re.Match) -> str:
    """Strip [REDACTED] from a heading-adjacent match, keeping the heading."""
    text = match.group(0)
    return re.sub(r"\[REDACTED\]\s*", "", text).strip()


def fix_word_boundary_redacted(text: str) -> str:
    """Remove [REDACTED] markers incorrectly inserted around English words.

    The formatter LLM sometimes inserts [REDACTED] mid-word, e.g.
    ``Re[REDACTED]ferences`` instead of ``References``, or inside
    transliterated names, e.g. ``Takayuki [REDACTED]okia`` instead of
    ``Takayuki Motoki``, or adjacent to section headings, e.g.
    ``References [REDACTED]``. This strips such markers while preserving
    legitimate [REDACTED] placeholders (e.g. ``aged [REDACTED] years``).
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
