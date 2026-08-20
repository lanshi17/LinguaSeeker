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


def test_three_letter_ref_with_stop_symbol_alt() -> None:
    """Three-letter ref with literal `*` alt also yields a one-letter ref alias."""
    aliases = expand_hgvs_aliases("p.Arg243*")
    assert "p.R243*" in aliases
    assert "p.Arg243*" in aliases


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
    assert normalize_hgvs_for_lookup("c.710C&gt;G") == "c.710C>G"
    assert "c.710C>G" in expand_hgvs_aliases("c . 7 1 0 C &gt; G")


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
    assert "p.S242R" in aliases
    assert "p.S346I" in aliases


def test_stop_codon_x_alias_maps_to_star() -> None:
    """Literature p.R243X (X stop) normalizes to the * form for lookup."""
    assert "p.R243*" in expand_hgvs_aliases("p.R243X")


def test_bare_one_letter_stop_alias_maps_to_prefixed_star() -> None:
    """Clinical tables often omit the p. prefix for protein stop variants."""
    aliases = expand_hgvs_aliases("R168X")

    assert "R168X" in aliases
    assert "p.R168*" in aliases


def test_bare_three_letter_stop_alias_maps_to_one_letter_star() -> None:
    """Bare three-letter protein stop variants are collapsed for lookup."""
    aliases = expand_hgvs_aliases("Arg168Ter")

    assert "Arg168Ter" in aliases
    assert "p.R168*" in aliases


def test_stop_word_alt_derives_star_alias() -> None:
    """p.Arg75stop derives the p.R75* one-letter alias."""
    aliases = expand_hgvs_aliases("p.Arg75stop")
    assert "p.R75*" in aliases


def test_three_letter_fs_alt_derives_one_letter_alias() -> None:
    """Three-letter frameshift p.Glu1309fs expands to the p.E1309fs alias."""
    assert "p.E1309fs" in expand_hgvs_aliases("p.Glu1309fs")


def test_extended_frameshift_protein_is_not_converted_to_missense() -> None:
    """p.Gly281AlafsTer20 must not collapse to the substitution p.G281A."""
    aliases = expand_hgvs_aliases("p.Gly281AlafsTer20")
    assert "p.G281fs" in aliases
    assert "p.G281A" not in aliases


def test_three_letter_del_alt_derives_one_letter_alias() -> None:
    """Three-letter deletion p.Phe508del expands to the p.F508del alias."""
