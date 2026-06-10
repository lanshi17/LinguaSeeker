"""Tests for ClinGen layer-3 value matching."""
from __future__ import annotations

from benchmark.layer3.evaluate import fuzzy_match_value


def test_fuzzy_match_value_treats_dash_variants_as_equivalent() -> None:
    assert fuzzy_match_value(
        "Charcot-Marie-Tooth disease axonal type 2N",
        "Charcot–Marie–Tooth disease axonal type 2N",
    )


def test_fuzzy_match_value_normalizes_curly_quotes_and_spacing() -> None:
    assert fuzzy_match_value("AARS2-related disease", "AARS2‑related  disease")


def test_fuzzy_match_value_normalizes_cjk_fullwidth_hyphen() -> None:
    assert fuzzy_match_value("AARS2-related disease", "AARS2－related disease")
