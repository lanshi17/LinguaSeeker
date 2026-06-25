"""Tests for annotation defect fixes (evaluation_type back-fill + re-annotation merge)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from benchmark.analysis.dataset_curation.fix_annotation_defects import (
    VARIANT_FIELD_IDS,
    evaluation_type_for_field,
)
from benchmark.analysis.dataset_curation.reannotate_unified import (
    _merge_reannotation,
    _source_expected_path,
)


# ---------------------------------------------------------------------------
# evaluation_type rule
# ---------------------------------------------------------------------------


def test_evaluation_type_variant_fields_are_precision_only() -> None:
    for field_id in ("A.variant_hgvs_c", "A.variant_hgvs_p", "A.variant_type", "A.functional_domain_or_hotspot"):
        assert evaluation_type_for_field(field_id) == "precision_only"


def test_evaluation_type_gene_disease_fields_are_precision_recall() -> None:
    for field_id in (
        "A.gene_symbol",
        "B.disease_diagnosis",
        "A.gene_disease_relationship",
        "B.mode_of_inheritance_reported",
    ):
        assert evaluation_type_for_field(field_id) == "precision_recall"


def test_evaluation_type_population_and_authority_are_precision_only() -> None:
    assert evaluation_type_for_field("D.allele_frequency") == "precision_only"
    assert evaluation_type_for_field("J.clinvar_assertion") == "precision_only"
    assert evaluation_type_for_field("D.gnomad_frequency") == "precision_only"


def test_variant_field_ids_set_is_non_empty_and_consistent() -> None:
    assert "A.variant_hgvs_p" in VARIANT_FIELD_IDS
    assert "A.gene_symbol" not in VARIANT_FIELD_IDS


# ---------------------------------------------------------------------------
# fix_annotation_defects on source data
# ---------------------------------------------------------------------------


def test_fix_clingen_evaluation_types_writes_missing_fields(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from benchmark.analysis.dataset_curation import fix_annotation_defects as fad

    # Build a fake clingen ground_truth root with one entry missing evaluation_type.
    gt_root = tmp_path / "ground_truth" / "clingen"
    entry_dir = gt_root / "clingen_000"
    entry_dir.mkdir(parents=True)
    expected = {
        "entry_id": "clingen_000",
        "expected_evidence": [
            {"field_id": "A.gene_symbol", "value": "AARS1"},
            {"field_id": "A.variant_hgvs_p", "value": "p.X1"},
        ],
    }
    (entry_dir / "expected.json").write_text(__import__("json").dumps(expected), encoding="utf-8")
    monkeypatch.setattr(fad, "GROUND_TRUTH_ROOT", tmp_path / "ground_truth" / "clingen")

    summary = fad.fix_clingen_evaluation_types(write=True)
    assert summary == {"clingen_000": 2}
    fixed = __import__("json").loads((entry_dir / "expected.json").read_text(encoding="utf-8"))
    types = {f["field_id"]: f["evaluation_type"] for f in fixed["expected_evidence"]}
    assert types["A.gene_symbol"] == "precision_recall"
    assert types["A.variant_hgvs_p"] == "precision_only"
    # minimal unified-schema fields added
    for f in fixed["expected_evidence"]:
        assert "candidates" in f
        assert f["source"] == "article"


def test_fix_clingen_preserves_existing_evaluation_type(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from benchmark.analysis.dataset_curation import fix_annotation_defects as fad

    gt_root = tmp_path / "ground_truth" / "clingen"
    entry_dir = gt_root / "clingen_001"
    entry_dir.mkdir(parents=True)
    expected = {
        "entry_id": "clingen_001",
        "expected_evidence": [
            {"field_id": "A.gene_symbol", "value": "X", "evaluation_type": "precision_recall"},
        ],
    }
    (entry_dir / "expected.json").write_text(__import__("json").dumps(expected), encoding="utf-8")
    monkeypatch.setattr(fad, "GROUND_TRUTH_ROOT", tmp_path / "ground_truth" / "clingen")
    summary = fad.fix_clingen_evaluation_types(write=True)
    assert summary == {}  # nothing to fix


# ---------------------------------------------------------------------------
# reannotate_unified merge + source path resolution
# ---------------------------------------------------------------------------


class _FakeExpected:
    """Minimal stand-in for the rett toolchain's RettExpectedJson pydantic model."""

    def __init__(self, evidence: list[dict[str, Any]], variants: list[dict[str, Any]]) -> None:
        self.expected_evidence = evidence
        self.variants = variants

    def model_dump(self) -> dict[str, Any]:
        return {"expected_evidence": self.expected_evidence, "variants": self.variants}


def test_merge_replaces_evidence_and_variants_preserving_metadata() -> None:
    existing = {
        "entry_id": "parkinson_004",
        "gene_symbol": "GIGYF2",
        "hgnc_id": "HGNC:11960",
        "disease_label": "Parkinson disease",
        "expected_standardization": {"gene": "HGNC:11960", "disease": "MONDO:0005180"},
        "expected_evidence": [{"field_id": "A.variant_hgvs_p", "value": "0.008,此处为等位基因频率的数据"}],
        "variants": [],
    }
    new = _FakeExpected(
        evidence=[{"field_id": "A.gene_symbol", "value": "GIGYF2", "evaluation_type": "precision_recall"}],
        variants=[{"hgvs_p": "p.Asn56Ser", "variant_type": "missense"}],
    )
    merged = _merge_reannotation(existing, new)
    # evidence + variants replaced
    assert len(merged["expected_evidence"]) == 1
    assert merged["expected_evidence"][0]["field_id"] == "A.gene_symbol"
    assert len(merged["variants"]) == 1
    assert merged["variants"][0]["hgvs_p"] == "p.Asn56Ser"
    # variants tagged with source
    assert merged["variants"][0]["source"] == "article"
    # metadata preserved
    assert merged["gene_symbol"] == "GIGYF2"
    assert merged["hgnc_id"] == "HGNC:11960"
    assert merged["expected_standardization"]["gene"] == "HGNC:11960"


def test_source_expected_path_resolves_dataset_and_original_id(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from benchmark.analysis.dataset_curation import reannotate_unified as ru

    monkeypatch.setattr(ru, "BENCHMARK_ROOT", tmp_path)
    unified = {"source_dataset": "parkinson", "original_entry_id": "parkinson_004"}
    path = _source_expected_path(unified)
    assert path == tmp_path / "data" / "ground_truth" / "parkinson" / "parkinson_004" / "expected.json"


def test_source_expected_path_returns_none_without_metadata() -> None:
    assert _source_expected_path({"source_dataset": "parkinson"}) is None
    assert _source_expected_path({"original_entry_id": "x"}) is None
