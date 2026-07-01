"""Tests for HGVS normalization utilities."""

from __future__ import annotations

import pytest

from benchmark.datasets.clinvar_fused.hgvs_normalize import (
    _parse_clinvar_hgvs_name,
    _parse_hgvs_from_clinvar_name,
    normalize_hgvs_c,
    normalize_hgvs_p,
    normalize_variant_type,
)


class TestNormalizeHgvsC:
    """Tests for coding HGVS normalization."""

    def test_transcript_prefix_removal(self) -> None:
        assert normalize_hgvs_c("NM_007294.4(BRCA1):c.5266dupC") == "c.5266dupC"

    def test_transcript_prefix_without_gene(self) -> None:
        assert normalize_hgvs_c("NM_000059.3:c.7397C>T") == "c.7397C>T"

    def test_whitespace_removal(self) -> None:
        assert normalize_hgvs_c("c.5266 dup C") == "c.5266dupC"

    def test_delins_case(self) -> None:
        assert normalize_hgvs_c("c.80_83DELINS") == "c.80_83delins"

    def test_nfkc_normalization(self) -> None:
        # Fullwidth characters
        assert normalize_hgvs_c("c.1A＞G") == "c.1A>G"

    def test_empty_string(self) -> None:
        assert normalize_hgvs_c("") == ""

    def test_bare_hgvs(self) -> None:
        assert normalize_hgvs_c("c.1234A>G") == "c.1234A>G"

    def test_complex_delins(self) -> None:
        result = normalize_hgvs_c("NM_014855.3(AP5Z1):c.80_83delinsTGCTGTAAACTGTAACTGTAAA")
        assert result == "c.80_83delinsTGCTGTAAACTGTAACTGTAAA"

    def test_genomic_prefix(self) -> None:
        assert normalize_hgvs_c("NC_000007.13:g.4820844del") == "g.4820844del"


class TestNormalizeHgvsP:
    """Tests for protein HGVS normalization."""

    def test_three_letter_to_one_letter(self) -> None:
        assert normalize_hgvs_p("p.Arg227Ter") == "p.R227*"

    def test_three_letter_no_prefix(self) -> None:
        assert normalize_hgvs_p("p.Gln1756ProfsTer74") == "p.Q1756Pfs*"

    def test_already_one_letter(self) -> None:
        assert normalize_hgvs_p("p.R227*") == "p.R227*"

    def test_stop_x(self) -> None:
        # X -> * for stop codons
        result = normalize_hgvs_p("p.R227X")
        assert "*" in result or "X" in result  # Depends on context

    def test_transcript_prefix(self) -> None:
        assert normalize_hgvs_p("NP_000050.1:p.Arg42Gly") == "p.R42G"

    def test_empty(self) -> None:
        assert normalize_hgvs_p("") == ""

    def test_fs_ter_pattern(self) -> None:
        result = normalize_hgvs_p("p.Gln1756ProfsTer74")
        assert "fs*" in result
        assert "Pro" not in result  # Should be converted to one-letter
        assert "Ter" not in result

    def test_stop_codon_at_end(self) -> None:
        assert normalize_hgvs_p("p.R227Ter") == "p.R227*"

    def test_stop_x_at_end(self) -> None:
        assert normalize_hgvs_p("p.R227X") == "p.R227*"

    def test_missense(self) -> None:
        assert normalize_hgvs_p("p.Val600Glu") == "p.V600E"


class TestNormalizeVariantType:
    """Tests for variant type normalization."""

    @pytest.mark.parametrize(
        "input_type,expected",
        [
            ("single nucleotide variant", "missense"),
            ("Single nucleotide variant", "missense"),
            ("SNV", "missense"),
            ("missense", "missense"),
            ("Missense variant", "missense"),
            ("nonsense", "nonsense"),
            ("Stop gained", "nonsense"),
            ("frameshift", "frameshift"),
            ("Frameshift variant", "frameshift"),
            ("splice site", "splice_site"),
            ("splice donor variant", "splice_site"),
            ("splice acceptor variant", "splice_site"),
            ("deletion", "deletion"),
            ("Deletion", "deletion"),
            ("insertion", "insertion"),
            ("dup", "dup"),
            ("Duplication", "dup"),
            ("Indel", "deletion"),
            ("copy number loss", "cnv"),
            ("CNV", "cnv"),
            ("synonymous", "synonymous"),
            ("intron variant", "other"),
            ("unknown_type", "other"),
            ("", ""),
        ],
    )
    def test_variant_type_mapping(self, input_type: str, expected: str) -> None:
        assert normalize_variant_type(input_type) == expected


class TestParseClinvarName:
    """Tests for ClinVar Name field parsing."""

    def test_standard_format(self) -> None:
        result = _parse_hgvs_from_clinvar_name("NM_007294.4(BRCA1):c.5266dupC (p.Gln1756ProfsTer74)")
        assert result["hgvs_c"] == "c.5266dupC"
        assert result["hgvs_p"] == "p.Gln1756ProfsTer74"

    def test_coding_only(self) -> None:
        result = _parse_hgvs_from_clinvar_name("NM_000059.3(BRCA2):c.7397C>T")
        assert result["hgvs_c"] == "c.7397C>T"
        assert result["hgvs_p"] == ""

    def test_complex_name(self) -> None:
        result = _parse_hgvs_from_clinvar_name(
            "NM_014855.3(AP5Z1):c.80_83delinsTGCTGTAAACTGTAACTGTAAA (p.Arg27_Ile28delinsLeuLeuTer)"
        )
        assert result["hgvs_c"] == "c.80_83delinsTGCTGTAAACTGTAACTGTAAA"
        assert result["hgvs_p"] == "p.Arg27_Ile28delinsLeuLeuTer"


class TestParseClinvarHgvsName:
    """Tests for full ClinVar Name parsing with normalization."""

    def test_full_parse(self) -> None:
        result = _parse_clinvar_hgvs_name("NM_007294.4(BRCA1):c.5266dupC (p.Gln1756ProfsTer74)")
        assert result["hgvs_c"] == "c.5266dupC"
        assert result["hgvs_p"] == "p.Gln1756ProfsTer74"
        assert result["normalized_c"] == "c.5266dupC"
        assert "Q" in result["normalized_p"]  # Gln -> Q
