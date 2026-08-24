"""HGVS variant notation normalizer for ClinVar alias matching.

Pure functions that convert between equivalent HGVS notation forms so that
lookups against ClinVar aliases match regardless of whether the source used
three-letter or one-letter amino acid codes, transcript prefixes, or list
literals.
"""

from __future__ import annotations

import html
import re
import unicodedata

from src.core.standardize_entities_and_align_knowledge.importers import AA3_TO_1

_SPACE_RE = re.compile(r"\s+")

# Inverse of AA3_TO_1; maps the stop symbol `*` back to the HGVS token `Ter`.
_AA1_TO_3 = {one: three for three, one in AA3_TO_1.items()}

# Compact one-letter canonical produced by `_convert_protein_3letter`, e.g.
# `p.R168*`, `p.G281fs`, `p.F508del`, `p.P237R`.
_ONE_LETTER_CANONICAL_RE = re.compile(r"p\.([A-Z])(\d+)(\*|fs|del|dup|ins|[A-Z])$")

# Effect tokens that stay verbatim instead of expanding to a three-letter code.
_LITERAL_ALT_TOKENS = frozenset({"fs", "del", "dup", "ins"})

# Three-letter protein variant, optional parentheses around the change.
# Groups: 1 = reference 3-letter code, 2 = position,
# 3 = alt 3-letter code, a stop token ("Ter", "*", "stop", "X"),
# or a literal effect token ("fs", "del", "dup", "ins").
_PROTEIN_3LETTER_RE = re.compile(r"p\.?\(?([A-Z][a-z]{2})(\d+)([A-Z][a-z]{2}|Ter|\*|stop|X|fs|del|dup|ins)\)?")

# RefSeq transcript prefix such as `NM_000059.4(BRCA2):` preceding a c. notation.
_TRANSCRIPT_PREFIX_RE = re.compile(r"^(?:NM|NR|XM|XR|NG)_[\d.]+(?:\([^)]+\))?:")

# Bracketed list literal wrapping quoted HGVS items, e.g. `['p.S242R','p.S346I']`.
_LIST_RE = re.compile(r"^\[([^\]]+)\]")

# Single quoted item inside a list literal.
_LIST_ITEM_RE = re.compile(r"['\"]([^'\"]+)['\"]")

# One-letter protein variant whose alt is the literal stop letter `X`, e.g. `p.R243X`.
# Literature often uses `X` for stop; ClinVar aliases use `*`, so emit the canonical `*` form.
_PROTEIN_1LETTER_STOP_RE = re.compile(r"p\.([A-Z])(\d+)X")

# Bare protein variants commonly appear in clinical tables without the `p.`
# prefix, e.g. `R168X` or `Arg168Ter`.
_BARE_PROTEIN_1LETTER_RE = re.compile(r"^([A-Z])(\d+)([A-Z*]|X)$")
_BARE_PROTEIN_3LETTER_RE = re.compile(r"^([A-Z][a-z]{2})(\d+)([A-Z][a-z]{2}|Ter|\*|stop|X|fs|del|dup|ins)$")


def normalize_hgvs_for_lookup(value: str) -> str:
    """Normalize an HGVS string for lookup: unescape, NFKC fold, then strip whitespace."""
    unescaped = html.unescape(value or "")
    return _SPACE_RE.sub("", unicodedata.normalize("NFKC", unescaped).strip())


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
    remainder = text[match.end() :]
    # p.Gly281AlafsTer20: the AA regex consumes Ala as a substitution.
    if remainder[:2].casefold() == "fs":
        return f"p.{ref1}{position}fs"
    if alt3 in ("Ter", "*", "stop", "X"):
        alt1 = "*"
    elif alt3 in ("fs", "del", "dup", "ins"):
        alt1 = alt3
    else:
        alt1 = AA3_TO_1.get(alt3)
    if alt1 is None:
        return None
    return f"p.{ref1}{position}{alt1}"


def _convert_protein_1letter_stop(text: str) -> str | None:
    """Convert a one-letter protein stop variant like `p.R243X` to the canonical `*` form.

    Returns `None` when `text` is not a one-letter protein stop variant.
    """
    match = _PROTEIN_1LETTER_STOP_RE.search(text)
    if match is None:
        return None
    return f"p.{match.group(1)}{match.group(2)}*"


def _convert_bare_protein(text: str) -> str | None:
    """Convert a bare protein variant into a prefixed one-letter HGVS alias."""
    one_letter = _BARE_PROTEIN_1LETTER_RE.fullmatch(text)
    if one_letter is not None:
        ref, position, alt = one_letter.group(1), one_letter.group(2), one_letter.group(3)
        return f"p.{ref}{position}{'*' if alt == 'X' else alt}"

    three_letter = _BARE_PROTEIN_3LETTER_RE.fullmatch(text)
    if three_letter is None:
        return None
    return _convert_protein_3letter(f"p.{text}")


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

    stop_converted = _convert_protein_1letter_stop(text)
    if stop_converted is not None:
        _add(stop_converted)

    bare_converted = _convert_bare_protein(text)
    if bare_converted is not None:
        _add(bare_converted)

    return aliases


def canonical_protein_hgvs(raw_text: str) -> str | None:
    """Return the HGVS-preferred three-letter form of a protein variant.

    HGVS recommends the three-letter amino acid code and `Ter` over the
    deprecated `X` stop symbol, so `R168X`, `p.R168*`, and `p.Arg168Ter` all
    canonicalize to `p.Arg168Ter`. Extended frameshift descriptions collapse
    to the position they start at (`p.Gly281AlafsTer20` -> `p.Gly281fs`).

    Returns `None` for coding (`c.`) notation and anything that does not
    reduce to a single-residue protein change.
    """
    for alias in expand_hgvs_aliases(raw_text):
        match = _ONE_LETTER_CANONICAL_RE.fullmatch(alias)
        if match is None:
            continue
        ref3 = _AA1_TO_3.get(match.group(1))
        alt = match.group(3)
        alt3 = alt if alt in _LITERAL_ALT_TOKENS else _AA1_TO_3.get(alt)
        # `p.R180X` has no amino acid named `X`; its `p.R180*` alias resolves it.
        if ref3 is None or alt3 is None:
            continue
        return f"p.{ref3}{match.group(2)}{alt3}"
    return None


def expand_hgvs_aliases(raw_text: str) -> list[str]:
    """Produce all normalized alias forms of an HGVS variant string.

    The normalized input is always the first alias; derived forms (stripped
    transcript prefix, one-letter protein conversion) follow in discovery order.
    Returns an empty list for empty input.
    """
    if not raw_text:
        return []
    return _expand_one(normalize_hgvs_for_lookup(raw_text))
