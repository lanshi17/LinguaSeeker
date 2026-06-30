"""Tests for field-specific normalization in benchmark matching.

Covers MOI normalization, gene-disease relationship normalization,
and the integration of field normalization into compare_evidence.
"""
from __future__ import annotations

import pytest

from benchmark.core.field_normalize import (
    normalize_field_for_matching,
    normalize_gene_disease_relationship,
    normalize_moi,
)
from benchmark.core.matching import compare_evidence


# ── MOI normalization ─────────────────────────────────────────────────


class TestNormalizeMoi:
    """Tests for mode-of-inheritance normalization."""

    @pytest.mark.parametrize("input_val,expected", [
        # Canonical codes pass through
        ("AD", "AD"),
        ("AR", "AR"),
        ("XL", "XL"),
        ("Mitochondrial", "Mitochondrial"),
        ("Somatic Mosaicism", "Somatic Mosaicism"),
        ("Undetermined", "Undetermined"),
        # Full descriptions → canonical
        ("autosomal dominant", "AD"),
        ("autosomal recessive", "AR"),
        ("autosomal dominant with reduced penetrance", "AD"),
        ("X-linked dominant", "XL"),
        ("X-linked recessive", "XL"),
        ("X-linked", "XL"),
        ("x-linked", "XL"),
        # Chinese
        ("X连锁显性遗传", "XL"),
        ("常染色体显性遗传", "AD"),
        ("常染色体隐性", "AR"),
        # Compound descriptions
        ("X-linked dominant; de novo mutation in this patient", "XL"),
        ("De novo in most RTT cases; X-linked", "XL"),
        # Empty
        ("", ""),
    ])
    def test_moi_mapping(self, input_val: str, expected: str) -> None:
        assert normalize_moi(input_val) == expected

    def test_moi_case_insensitive(self) -> None:
        assert normalize_moi("ad") == "AD"
        assert normalize_moi("Ad") == "AD"

    def test_moi_unknown_returns_uppercase(self) -> None:
        result = normalize_moi("polygenic")
        assert result == "POLYGENIC"


# ── Gene-disease relationship normalization ───────────────────────────


class TestNormalizeGeneDiseaseRelationship:
    """Tests for gene-disease relationship normalization."""

    @pytest.mark.parametrize("input_val,expected", [
        # Canonical enum values
        ("causative", "causative"),
        ("uncertain", "uncertain"),
        ("disputed", "disputed"),
        ("refuted", "refuted"),
        ("unknown", "unknown"),
        # Free text → canonical
        ("MECP2 mutations cause Rett syndrome", "causative"),
        ("MECP2 is responsible for Rett syndrome", "causative"),
        ("Rett syndrome is due mainly to loss-of-function variations", "causative"),
        ("The relationship is uncertain", "uncertain"),
        ("Evidence is limited", "uncertain"),
        ("The association is disputed", "disputed"),
        ("No evidence of association", "refuted"),
        ("Gene not associated with disease", "refuted"),
        # Empty
        ("", ""),
    ])
    def test_gdr_mapping(self, input_val: str, expected: str) -> None:
        assert normalize_gene_disease_relationship(input_val) == expected

    @pytest.mark.parametrize("input_val,expected", [
        ("associated", "causative"),
        ("related", "causative"),
        ("linked", "causative"),
    ])
    def test_gdr_associated_synonyms(self, input_val: str, expected: str) -> None:
        """Broad relationship terms normalize to 'causative' for monogenic disease genes."""
        assert normalize_gene_disease_relationship(input_val) == expected

    def test_gdr_refuted_takes_priority_over_causative(self) -> None:
        """'refuted' patterns are checked before 'causative' to avoid
        matching 'causative' in 'refuted as causative'."""
        result = normalize_gene_disease_relationship("refuted as causative")
        assert result == "refuted"


# ── Dispatch ──────────────────────────────────────────────────────────


class TestNormalizeFieldForMatching:
    """Tests for the field_id dispatch function."""

    def test_hgvs_p_dispatch(self) -> None:
        assert normalize_field_for_matching("A.variant_hgvs_p", "p.Ile359Leu") == "p.I359L"

    def test_hgvs_c_dispatch(self) -> None:
        assert normalize_field_for_matching("A.variant_hgvs_c", "NM_000059.3:c.7397C>T") == "c.7397C>T"

    def test_moi_dispatch(self) -> None:
        assert normalize_field_for_matching("B.mode_of_inheritance_reported", "autosomal dominant") == "AD"

    def test_moi_k_field_dispatch(self) -> None:
        assert normalize_field_for_matching("K.mode_of_inheritance", "AR") == "AR"

    def test_variant_type_dispatch(self) -> None:
        assert normalize_field_for_matching("A.variant_type", "single nucleotide variant") == "missense"

    def test_gdr_dispatch(self) -> None:
        assert normalize_field_for_matching("A.gene_disease_relationship", "causative") == "causative"

    def test_unknown_field_returns_unchanged(self) -> None:
        assert normalize_field_for_matching("A.gene_symbol", "BRCA1") == "BRCA1"

    def test_empty_value_returns_empty(self) -> None:
        assert normalize_field_for_matching("A.variant_hgvs_p", "") == ""


# ── Integration: compare_evidence with field normalization ────────────


class TestCompareEvidenceFieldNormalized:
    """Integration tests for field normalization in compare_evidence."""

    def test_hgvs_p_three_letter_matches_one_letter(self) -> None:
        """p.Ile359Leu (literature) matches p.I359L (ground truth)."""
        expected = [{"field_id": "A.variant_hgvs_p", "value": "p.I359L"}]
        extracted = [
            {"field_id": "A.variant_hgvs_p", "status": "found", "value": "p.Ile359Leu", "confidence": 0.9},
        ]
        matches = compare_evidence(expected, extracted)
        assert len(matches) == 1
        assert matches[0].matched is True
        assert matches[0].match_type == "field_normalized"

    def test_hgvs_p_db_value_payload_matches_three_letter_gold(self) -> None:
        """DB row value payloads should be unwrapped before HGVS matching."""
        expected = [{"field_id": "A.variant_hgvs_p", "value": "p.Arg69Cys"}]
        extracted = [
            {"field_id": "A.variant_hgvs_p", "status": "found", "value": {"value": "p.R69C"}, "confidence": 0.45},
        ]
        matches = compare_evidence(expected, extracted)
        assert len(matches) == 1
        assert matches[0].matched is True
        assert matches[0].match_type == "field_normalized"

    def test_hgvs_p_exact_match_takes_priority_over_field_normalized(self) -> None:
        """When exact match exists, field_normalized is not used."""
        expected = [{"field_id": "A.variant_hgvs_p", "value": "p.R227*"}]
        extracted = [
            {"field_id": "A.variant_hgvs_p", "status": "found", "value": "p.R227*", "confidence": 0.9},
        ]
        matches = compare_evidence(expected, extracted)
        assert matches[0].matched is True
        assert matches[0].match_type == "exact"

    def test_moi_abbreviation_matches_full_description(self) -> None:
        """AD (ClinGen ground truth) matches 'autosomal dominant with reduced penetrance'."""
        expected = [{"field_id": "B.mode_of_inheritance_reported", "value": "AD"}]
        extracted = [
            {"field_id": "B.mode_of_inheritance_reported", "status": "found",
             "value": "autosomal dominant with reduced penetrance", "confidence": 0.85},
        ]
        matches = compare_evidence(expected, extracted)
        assert len(matches) == 1
        assert matches[0].matched is True
        assert matches[0].match_type == "field_normalized"

    def test_moi_xlinked_matches_x_linked_dominant(self) -> None:
        """XL (ClinGen) matches 'X-linked dominant'."""
        expected = [{"field_id": "B.mode_of_inheritance_reported", "value": "XL"}]
        extracted = [
            {"field_id": "B.mode_of_inheritance_reported", "status": "found",
             "value": "X-linked dominant", "confidence": 0.9},
        ]
        matches = compare_evidence(expected, extracted)
        assert matches[0].matched is True
        assert matches[0].match_type == "field_normalized"

    def test_variant_type_normalizes_clinvar_to_enum(self) -> None:
        """'single nucleotide variant' (ClinVar) matches 'missense' (pipeline enum)."""
        expected = [{"field_id": "A.variant_type", "value": "missense"}]
        extracted = [
            {"field_id": "A.variant_type", "status": "found",
             "value": "single nucleotide variant", "confidence": 0.8},
        ]
        matches = compare_evidence(expected, extracted)
        assert matches[0].matched is True
        assert matches[0].match_type == "field_normalized"

    def test_gene_disease_relationship_causative_matches_free_text(self) -> None:
        """'causative' (ClinGen enum) matches 'MECP2 mutations cause Rett syndrome'."""
        expected = [{"field_id": "A.gene_disease_relationship", "value": "causative"}]
        extracted = [
            {"field_id": "A.gene_disease_relationship", "status": "found",
             "value": "MECP2 mutations cause Rett syndrome", "confidence": 0.9},
        ]
        matches = compare_evidence(expected, extracted)
        assert matches[0].matched is True
        assert matches[0].match_type == "field_normalized"

    def test_non_normalized_field_still_works(self) -> None:
        """Fields without specialized normalization use standard matching."""
        expected = [{"field_id": "A.gene_symbol", "value": "BRCA1"}]
        extracted = [
            {"field_id": "A.gene_symbol", "status": "found", "value": "BRCA1", "confidence": 0.95},
        ]
        matches = compare_evidence(expected, extracted)
        assert matches[0].matched is True
        assert matches[0].match_type == "exact"

    def test_moi_mismatch_remains_unmatched(self) -> None:
        """AD does not match AR."""
        expected = [{"field_id": "B.mode_of_inheritance_reported", "value": "AD"}]
        extracted = [
            {"field_id": "B.mode_of_inheritance_reported", "status": "found",
             "value": "autosomal recessive", "confidence": 0.9},
        ]
        matches = compare_evidence(expected, extracted)
        assert len(matches) == 1
        assert matches[0].matched is False
        assert matches[0].match_type == "wrong_value"

    def test_gdr_associated_matches_causative(self) -> None:
        """'associated' (ground truth) matches 'causative' (system extraction)."""
        expected = [{"field_id": "A.gene_disease_relationship", "value": "associated"}]
        extracted = [
            {"field_id": "A.gene_disease_relationship", "status": "found",
             "value": "causative", "confidence": 0.9},
        ]
        matches = compare_evidence(expected, extracted)
        assert len(matches) == 1
        assert matches[0].matched is True
        assert matches[0].match_type == "field_normalized"

    def test_gdr_associated_matches_susceptibility(self) -> None:
        """'associated' (ground truth) should match 'susceptibility' for risk genes like GBA."""
        expected = [{"field_id": "A.gene_disease_relationship", "value": "associated"}]
        extracted = [
            {"field_id": "A.gene_disease_relationship", "status": "found",
             "value": "susceptibility", "confidence": 0.85},
        ]
        matches = compare_evidence(expected, extracted)
        assert len(matches) == 1
        assert matches[0].matched is True
