"""Tests for HGVS variant notation normalizer used in ClinVar alias matching."""
from __future__ import annotations

from src.core.standardize_entities_and_align_knowledge.hgvs_normalizer import (
    expand_hgvs_aliases,
    normalize_hgvs_for_lookup,
)


def test_three_letter_protein_to_one_letter() -> None:
    """Three-letter protein notation expands to a one-letter alias."""
    assert "p.E292V" in expand_hgvs_aliases("p.(Glu292Val)")


def test_one_letter_protein_passes_through() -> None:
    """One-letter protein notation passes through unchanged."""
    assert "p.Arg243*" in expand_hgvs_aliases("p.Arg243*")


def test_dna_notation_strips_transcript_prefix() -> None:
    """Transcript-prefixed DNA notation also yields its bare c. form."""
    assert "c.5946del" in expand_hgvs_aliases("NM_000059.4(BRCA2):c.5946del")


def test_bare_dna_notation_passes_through() -> None:
    """Bare DNA notation without a transcript prefix passes through unchanged."""
    assert "c.727C>T" in expand_hgvs_aliases("c.727C>T")


def test_three_letter_with_parentheses() -> None:
    """Parenthesized three-letter protein notation expands to a one-letter alias."""
    assert "p.H97R" in expand_hgvs_aliases("p.His97Arg")


def test_stop_codon_three_letter_to_one_letter() -> None:
    """Three-letter stop codon `Ter` expands to the one-letter `*` alias."""
    assert "p.W159*" in expand_hgvs_aliases("p.Trp159Ter")


def test_normalize_strips_whitespace_and_applies_nfkc() -> None:
    """Lookup normalization removes all whitespace and applies Unicode NFKC."""
    assert normalize_hgvs_for_lookup("  p. Arg243*  ") == "p.Arg243*"


def test_empty_input_returns_empty() -> None:
    """Empty input yields no aliases and an empty normalized lookup key."""
    assert expand_hgvs_aliases("") == []
    assert normalize_hgvs_for_lookup("") == ""


def test_non_hgvs_input_passes_through() -> None:
    """Non-HGVS text passes through as its sole alias."""
    assert expand_hgvs_aliases("BRCA1") == ["BRCA1"]


def test_list_input_is_joined() -> None:
    """Bracketed list of quoted HGVS items splits and expands each member."""
    aliases = expand_hgvs_aliases("['p.S242R','p.S346I']")
    assert "p.S242R" in aliases
    assert "p.S346I" in aliases
