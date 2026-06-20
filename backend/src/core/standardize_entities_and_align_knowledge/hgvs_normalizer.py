"""HGVS variant notation normalizer for ClinVar alias matching.

Pure functions that convert between equivalent HGVS notation forms so that
lookups against ClinVar aliases match regardless of whether the source used
three-letter or one-letter amino acid codes, transcript prefixes, or list
literals.
"""
from __future__ import annotations

import re
import unicodedata

from src.core.standardize_entities_and_align_knowledge.importers import AA3_TO_1

_SPACE_RE = re.compile(r"\s+")

# Three-letter protein variant, optional parentheses around the change.
# Groups: 1 = reference 3-letter code, 2 = position,
# 3 = alt 3-letter code, "Ter", or the literal stop symbol "*".
_PROTEIN_3LETTER_RE = re.compile(r"p\.?\(?([A-Z][a-z]{2})(\d+)([A-Z][a-z]{2}|Ter|\*)\)?")

# RefSeq transcript prefix such as `NM_000059.4(BRCA2):` preceding a c. notation.
_TRANSCRIPT_PREFIX_RE = re.compile(r"^(?:NM|NR|XM|XR|NG)_[\d.]+(?:\([^)]+\))?:")

# Bracketed list literal wrapping quoted HGVS items, e.g. `['p.S242R','p.S346I']`.
_LIST_RE = re.compile(r"^\[([^\]]+)\]")

# Single quoted item inside a list literal.
_LIST_ITEM_RE = re.compile(r"['\"]([^'\"]+)['\"]")


def normalize_hgvs_for_lookup(value: str) -> str:
    """Normalize an HGVS string for lookup: NFKC fold then strip all whitespace."""
    return _SPACE_RE.sub("", unicodedata.normalize("NFKC", value or "").strip())


def _convert_protein_3letter(text: str) -> str | None:
    """Convert a three-letter protein variant to its one-letter alias form.

    Returns `None` when `text` is not a three-letter protein variant or when the
    amino acid codes are not recognized.
    """
    match = _PROTEIN_3LETTER_RE.search(text)
    if match is None:
        return None
    ref3, position, alt3 = match.group(1), match.group(2), match.group(3)
    ref1 = AA3_TO_1.get(ref3)
    if ref1 is None:
        return None
    alt1 = "*" if alt3 in ("Ter", "*") else AA3_TO_1.get(alt3)
    if alt1 is None:
        return None
    return f"p.{ref1}{position}{alt1}"


def _expand_one(text: str) -> list[str]:
    """Expand a single normalized HGVS string into its alias forms."""
    aliases: list[str] = []

    def _add(candidate: str) -> None:
        if candidate and candidate not in aliases:
            aliases.append(candidate)

    list_match = _LIST_RE.match(text)
    if list_match is not None:
        for item in _LIST_ITEM_RE.findall(list_match.group(1)):
            for alias in _expand_one(normalize_hgvs_for_lookup(item)):
                _add(alias)
        return aliases

    _add(text)

    stripped = _TRANSCRIPT_PREFIX_RE.sub("", text, count=1)
    if stripped != text:
        for alias in _expand_one(stripped):
            _add(alias)

    converted = _convert_protein_3letter(text)
    if converted is not None:
        _add(converted)

    return aliases


def expand_hgvs_aliases(raw_text: str) -> list[str]:
    """Produce all normalized alias forms of an HGVS variant string.

    The normalized input is always the first alias; derived forms (stripped
    transcript prefix, one-letter protein conversion) follow in discovery order.
    Returns an empty list for empty input.
    """
    if not raw_text:
        return []
    return _expand_one(normalize_hgvs_for_lookup(raw_text))
