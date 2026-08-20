"""Tests for Phase 3 standardization normalization helpers."""

from __future__ import annotations

from src.core.standardize_entities_and_align_knowledge.normalizers import (
    make_entity_scope_hash,
    make_target_scope_bindings,
    normalize_disease_lookup_text,
    normalize_gene_symbol,
    normalize_lookup_text,
    normalize_variant_text,
)


def test_lookup_normalization_is_stable() -> None:
    """Lookup normalization trims whitespace and folds case deterministically."""
    assert normalize_lookup_text("  Charcot-Marie Tooth  ") == "charcot-marie tooth"


def test_lookup_normalization_applies_nfkc_and_collapses_consecutive_spaces() -> None:
    """Lookup normalization applies Unicode NFKC and merges repeated whitespace."""
    assert normalize_lookup_text("ＭＥＴＡＢＯＬＩＣ\u3000 disorder   syndrome") == "metabolic disorder syndrome"


def test_lookup_normalization_returns_empty_string_for_empty_input() -> None:
    """Lookup normalization handles empty input without special casing downstream."""
    assert normalize_lookup_text("") == ""


def test_normalize_gene_symbol_returns_uppercase_lookup_key() -> None:
    """Gene normalization composes lookup normalization with uppercase HGNC matching."""
    assert normalize_gene_symbol(" brca1 ") == "BRCA1"


def test_normalize_gene_symbol_applies_nfkc_before_uppercase() -> None:
    """Gene normalization canonicalizes full-width characters before uppercasing."""
    assert normalize_gene_symbol("ｂｒｃａ２") == "BRCA2"


def test_normalize_variant_text_removes_all_whitespace() -> None:
    """Variant normalization strips interstitial whitespace for exact alias matching."""
    assert normalize_variant_text(" NM_000059.4 ( BRCA2 ) : c.5946del ") == "NM_000059.4(BRCA2):c.5946del"


def test_normalize_variant_text_applies_nfkc_and_handles_empty_input() -> None:
    """Variant normalization folds Unicode width and leaves empty values stable."""
    assert normalize_variant_text("ｒｓ８０３５９５５０") == "rs80359550"
    assert normalize_variant_text("") == ""


def test_entity_scope_hash_is_order_independent() -> None:
    """Entity-scope hashes are stable regardless of binding order."""
    left = make_entity_scope_hash(
        [
            ("target", "ClinVarVariation:123"),
            ("subject", "HGNC:1100"),
        ],
    )
    right = make_entity_scope_hash(
        [
            ("subject", "HGNC:1100"),
            ("target", "ClinVarVariation:123"),
        ],
    )

    assert left == right


def test_entity_scope_hash_for_empty_bindings_matches_empty_stable_value() -> None:
    """Entity-scope hashing handles empty bindings deterministically."""
    assert make_entity_scope_hash([]) == ("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")


def test_normalize_lookup_text_preserves_chinese() -> None:
    """Chinese characters pass through normalization unchanged for alias lookup."""
    assert normalize_lookup_text("法布雷病") == "法布雷病"


def test_normalize_variant_text_preserves_protein_notation() -> None:
    """Protein variant notation like p.R227X is preserved for lookup."""
    assert normalize_variant_text("p.R227X") == "p.R227X"


def test_normalize_disease_lookup_text_maps_chinese_to_english() -> None:
    """Chinese disease names are mapped to English equivalents for terminology lookup."""
    assert normalize_disease_lookup_text("法布雷病") == "fabry disease"


def test_normalize_disease_lookup_text_passes_through_english() -> None:
    """English disease names pass through cross-lingual normalization unchanged."""
    assert normalize_disease_lookup_text("Fabry disease") == "fabry disease"


def test_normalize_disease_lookup_text_passes_through_unknown_chinese() -> None:
    """Unknown Chinese disease names pass through as normalized lookup text."""
    assert normalize_disease_lookup_text("未知疾病") == "未知疾病"


def test_target_scope_bindings_change_entity_scope_hash() -> None:
    from src.core.evidence_extraction.contracts import (
        ExtractionTarget,
    )

    abca3 = ExtractionTarget(gene_symbol="ABCA3", disease_name="ABCA3 deficiency")
    cftr = ExtractionTarget(gene_symbol="CFTR", disease_name="cystic fibrosis")
    entity_bindings = [("subject", "HGNC:33"), ("context", "MONDO:0000001")]

    assert make_entity_scope_hash([*make_target_scope_bindings(abca3), *entity_bindings]) != (
        make_entity_scope_hash([*make_target_scope_bindings(cftr), *entity_bindings])
    )


def test_target_scope_bindings_include_coding_variant_when_protein_hgvs_is_absent() -> None:
    """A c.-only target remains distinct in downstream entity scope hashes."""
    from src.core.evidence_extraction.contracts import ExtractionTarget

    target = ExtractionTarget(
        gene_symbol="MECP2",
        disease_name="Rett syndrome",
        variant_hgvs_c="c.710C>G",
    )

    assert ("target_variant_c", "c.710C>G") in make_target_scope_bindings(target)
