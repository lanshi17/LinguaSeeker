"""Tests for deterministic internal variant identifiers."""

from __future__ import annotations

from src.core.standardize_entities_and_align_knowledge.variant_id import (
    make_internal_variant_id,
)


def test_internal_variant_id_stable_and_prefixed() -> None:
    vid = make_internal_variant_id("c.4748T>G", "DICER1")
    assert vid.startswith("internal:variant:")
    # 48-bit (12 hex char) digest follows the prefix.
    assert len(vid) == len("internal:variant:") + 12
    assert vid == make_internal_variant_id("c.4748T>G", "DICER1")
    assert vid != make_internal_variant_id("c.4748T>G", "BRCA1")


def test_internal_variant_id_normalizes_input() -> None:
    assert make_internal_variant_id(" c.4748T>G ", "dicer1") == make_internal_variant_id("c.4748T>G", "DICER1")


def test_internal_variant_id_empty_gene() -> None:
    vid = make_internal_variant_id("p.A168T", "")
    assert vid.startswith("internal:variant:")
    # different from a gene-bearing id
    assert vid != make_internal_variant_id("p.A168T", "DRD4")
