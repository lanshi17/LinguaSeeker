"""Tests for the unified dataset builder field-supplementation logic.

Covers clinvar_fused nested-block lifting, HGNC + ClinGen CSV back-fill (with
approved-symbol fallback), source-language / PDF resolution, fidelity-preserving
variant unification, expected_entities derivation, evaluation_config generation,
and EuropePMC cache-driven back-fill. Filesystem paths are monkeypatched so the
real benchmark tree is never touched.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from benchmark.analysis.dataset_curation import build_unified_dataset as bud
from benchmark.analysis.dataset_curation.build_unified_dataset import (
    BuildContext,
    _unify_variants,
    unify_entry,
)


def _ctx(
    *,
    hgnc_aliases: dict[str, dict[str, Any]] | None = None,
    clingen_records: dict[tuple[str, str], dict[str, str]] | None = None,
    field_layer: dict[str, str] | None = None,
    pmid_cache: dict[str, dict[str, str]] | None = None,
) -> BuildContext:
    return BuildContext(
        hgnc_aliases=hgnc_aliases or {},
        clingen_records=clingen_records or {},
        field_layer=field_layer
        or {
            "A.gene_symbol": "gene_disease_fields",
            "B.disease_diagnosis": "gene_disease_fields",
            "A.gene_disease_relationship": "gene_disease_fields",
            "B.mode_of_inheritance_reported": "gene_disease_fields",
            "A.variant_hgvs_c": "variant_fields",
            "A.variant_hgvs_p": "variant_fields",
            "A.variant_type": "variant_fields",
            "J.clinvar_assertion": "variant_fields",
            "B.hpo_terms": "clinical_fields",
            "C.de_novo_status": "clinical_fields",
        },
        pmid_cache=pmid_cache or {},
    )


def _entry(dataset: str, original_id: str = "x_000", **extra: Any) -> dict[str, Any]:
    base = {
        "unified_id": "gs_000",
        "original_entry_id": original_id,
        "source_dataset": dataset,
        "gold_source": "database" if dataset in {"clingen", "clinvar_fused"} else "article",
        "gene_symbol": "CFTR",
        "hgnc_id": "HGNC:1884",
        "disease_label": "cystic fibrosis",
        "mondo_id": "MONDO:0009061",
        "source_pmid": "111",
        "source_doi": "",
        "source_title": "A Title",
        "source_pdf_path": "",
        "expected_json_path": "benchmark/data/ground_truth/clingen/x_000/expected.json",
        "source_md_path": "benchmark/data/ground_truth/clingen/x_000/source.md",
    }
    base.update(extra)
    return base


# ---------------------------------------------------------------------------
# clinvar_fused nested-block lifting
# ---------------------------------------------------------------------------


def test_lift_clinvar_fused_nested_clingen_block() -> None:
    expected = {
        "entry_id": "fused_000",
        "clingen": {
            "gene_symbol": "CFTR",
            "hgnc_id": "HGNC:1884",
            "disease_label": "cystic fibrosis",
            "mondo_id": "MONDO:0009061",
            "moi": "AR",
            "classification": "Definitive",
            "gcep": "General GCEP",
            "classification_date": "2022-06-01T05:00:00.000Z",
            "report_url": "https://example.org/report",
        },
        "clinvar_variants": [],
        "expected_evidence": [{"field_id": "A.gene_symbol", "value": "CFTR"}],
        "expected_standardization": {"gene": "HGNC:1884", "disease": "MONDO:0009061"},
        "expected_entities": {},
    }
    unified = unify_entry(_entry("clinvar_fused", "fused_000"), expected, _ctx())
    assert unified["gene_symbol"] == "CFTR"
    assert unified["hgnc_id"] == "HGNC:1884"
    assert unified["disease_label"] == "cystic fibrosis"
    assert unified["mondo_id"] == "MONDO:0009061"
    assert unified["moi"] == "AR"
    assert unified["classification"] == "Definitive"
    assert unified["gcep"] == "General GCEP"
    assert unified["clingen_report_url"] == "https://example.org/report"
    assert unified["backfilled"]["gene_symbol"] == "lifted_clingen_block"
    assert unified["backfilled"]["moi"] == "lifted_clingen_block"


# ---------------------------------------------------------------------------
# parkinson HGNC + ClinGen CSV back-fill
# ---------------------------------------------------------------------------


def test_parkinson_hgnc_and_moi_backfill() -> None:
    expected = {
        "entry_id": "parkinson_000",
        "gene_symbol": "PRKN",
        "disease_label": "Parkinson disease",
        "mondo_id": "MONDO:0005180",
        "source_pmid": "16227559",
        "source_doi": "10.1/x",
        "expected_evidence": [{"field_id": "A.gene_symbol", "value": "PRKN"}],
        "expected_standardization": {"gene": "PRKN", "disease": "MONDO:0005180"},
        "expected_entities": {"gene": {"text": "PRKN"}, "disease": {"text": "Parkinson disease"}},
    }
    ctx = _ctx(
        hgnc_aliases={"PRKN": {"approved": "PRKN", "hgnc_id": "HGNC:8607", "aliases": [], "previous": ["PARK2"]}},
        clingen_records={
            ("PRKN", "MONDO:0005180"): {
                "gene_symbol": "PRKN",
                "hgnc_id": "HGNC:8607",
                "disease_label": "Parkinson disease",
                "mondo_id": "MONDO:0005180",
                "moi": "AR",
                "classification": "Definitive",
                "gcep": "PD GCEP",
                "classification_date": "2023-01-18T19:00:00.000Z",
                "clingen_report_url": "https://example.org/prkn",
            }
        },
    )
    unified = unify_entry(_entry("parkinson", "parkinson_000"), expected, ctx)
    assert unified["hgnc_id"] == "HGNC:8607"
    assert unified["moi"] == "AR"
    assert unified["classification"] == "Definitive"
    assert unified["gcep"] == "PD GCEP"
    assert unified["backfilled"]["hgnc_id"] == "hgnc_file"
    assert unified["backfilled"]["moi"] == "clingen_csv"
    # standardization gene should be normalized to HGNC id.
    assert unified["expected_standardization"]["gene"] == "HGNC:8607"


def test_clingen_lookup_falls_back_to_approved_symbol() -> None:
    """GBA is stored in ClinGen under its approved symbol GBA1."""
    expected = {
        "entry_id": "parkinson_012",
        "gene_symbol": "GBA",
        "disease_label": "Parkinson disease",
        "mondo_id": "MONDO:0005180",
        "source_pmid": "26117366",
        "expected_evidence": [{"field_id": "A.gene_symbol", "value": "GBA"}],
        "expected_standardization": {"gene": "GBA", "disease": "MONDO:0005180"},
        "expected_entities": {},
    }
    ctx = _ctx(
        hgnc_aliases={"GBA": {"approved": "GBA1", "hgnc_id": "HGNC:4177", "aliases": [], "previous": ["GBA"]}},
        clingen_records={
            ("GBA1", "MONDO:0005180"): {
                "gene_symbol": "GBA1",
                "hgnc_id": "HGNC:4177",
                "disease_label": "Parkinson disease",
                "mondo_id": "MONDO:0005180",
                "moi": "AD",
                "classification": "Definitive",
                "gcep": "PD GCEP",
                "classification_date": "",
                "clingen_report_url": "",
            }
        },
    )
    unified = unify_entry(_entry("parkinson", "parkinson_012"), expected, ctx)
    assert unified["hgnc_id"] == "HGNC:4177"
    assert unified["moi"] == "AD"  # resolved via approved-symbol fallback


def test_missing_clingen_record_leaves_moi_empty_with_note() -> None:
    expected = {
        "entry_id": "parkinson_017",
        "gene_symbol": "GIGYF2",
        "disease_label": "Parkinson disease",
        "mondo_id": "MONDO:0005180",
        "source_pmid": "18358451",
        "expected_evidence": [{"field_id": "A.gene_symbol", "value": "GIGYF2"}],
        "expected_standardization": {"gene": "GIGYF2", "disease": "MONDO:0005180"},
        "expected_entities": {},
    }
    ctx = _ctx(
        hgnc_aliases={"GIGYF2": {"approved": "GIGYF2", "hgnc_id": "HGNC:11960", "aliases": [], "previous": []}},
        clingen_records={},  # no ClinGen record for GIGYF2
    )
    unified = unify_entry(_entry("parkinson", "parkinson_017"), expected, ctx)
    assert unified["hgnc_id"] == "HGNC:11960"
    assert unified["moi"] == ""
    assert "no ClinGen record" in unified["notes"]


# ---------------------------------------------------------------------------
# source_language back-fill
# ---------------------------------------------------------------------------


def test_source_language_default_en_for_clingen(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(bud, "BENCHMARK_ROOT", tmp_path)
    expected = {
        "entry_id": "clingen_000",
        "gene_symbol": "AARS1",
        "hgnc_id": "HGNC:20",
        "disease_label": "CMT2N",
        "mondo_id": "MONDO:0013212",
        "moi": "AD",
        "source_pmid": "111",
        "expected_evidence": [{"field_id": "A.gene_symbol"}],
        "expected_standardization": {"gene": "HGNC:20", "disease": "MONDO:0013212"},
        "expected_entities": {},
    }
    unified = unify_entry(_entry("clingen", "clingen_000"), expected, _ctx())
    assert unified["source_language"] == "en"
    assert unified["backfilled"]["source_language"] == "default_en"


def test_source_language_from_parkinson_meta_json(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(bud, "BENCHMARK_ROOT", tmp_path)
    meta_dir = tmp_path / "data" / "ground_truth" / "parkinson" / "parkinson_000"
    meta_dir.mkdir(parents=True)
    (meta_dir / "meta.json").write_text(json.dumps({"language": "en"}), encoding="utf-8")
    expected = {
        "entry_id": "parkinson_000",
        "gene_symbol": "PRKN",
        "hgnc_id": "HGNC:8607",
        "disease_label": "Parkinson disease",
        "mondo_id": "MONDO:0005180",
        "moi": "AR",
        "source_pmid": "16227559",
        "expected_evidence": [{"field_id": "A.gene_symbol"}],
        "expected_standardization": {"gene": "HGNC:8607", "disease": "MONDO:0005180"},
        "expected_entities": {},
    }
    ctx = _ctx(hgnc_aliases={"PRKN": {"approved": "PRKN", "hgnc_id": "HGNC:8607", "aliases": [], "previous": []}})
    unified = unify_entry(_entry("parkinson", "parkinson_000"), expected, ctx)
    assert unified["source_language"] == "en"
    assert unified["backfilled"]["source_language"] == "meta_json"


# ---------------------------------------------------------------------------
# variant unification (fidelity-preserving)
# ---------------------------------------------------------------------------


def test_unify_variants_merges_rett_and_clinvar_preserving_fields() -> None:
    expected = {
        "variants": [
            {
                "hgvs_p": "p.R294X",
                "variant_type": "nonsense",
                "clinical_significance": "pathogenic",
                "exon": "4",
                "domain": "TRD",
                "hgvs_c": "",
            }
        ],
        "clinvar_variants": [
            {
                "variation_id": "7105",
                "hgvs_name": "NM:c.1521del",
                "hgvs_c": "c.1521del",
                "hgvs_p": "p.Phe508del",
                "variant_type": "deletion",
                "clinical_significance": "Pathogenic",
                "rsid": "rs1",
                "review_status": "practice guideline",
                "review_stars": 4,
                "phenotype_ids": "MONDO:1",
                "phenotype_list": "CF",
            }
        ],
    }
    variants = _unify_variants(expected, "clinvar_fused")
    assert len(variants) == 2
    rett_v = next(v for v in variants if v["source"] == "rett")
    assert rett_v["hgvs_p"] == "p.R294X"
    assert rett_v["domain"] == "TRD"
    assert rett_v["exon"] == "4"
    clinvar_v = next(v for v in variants if v["source"] == "clinvar")
    assert clinvar_v["variation_id"] == "7105"
    assert clinvar_v["rsid"] == "rs1"
    assert clinvar_v["review_stars"] == 4
    assert clinvar_v["phenotype_list"] == "CF"


def test_expected_entities_derived_for_rett() -> None:
    expected = {
        "entry_id": "rett_001",
        "gene_symbol": "MECP2",
        "hgnc_id": "HGNC:6992",
        "disease_label": "Rett syndrome",
        "mondo_id": "MONDO:0010726",
        "moi": "XD",
        "source_doi": "10.1/x",
        "expected_evidence": [{"field_id": "A.gene_symbol"}],
        "expected_standardization": {"gene": "HGNC:6992", "disease": "MONDO:0010726"},
        "expected_entities": {},  # rett entries start empty
        "variants": [{"hgvs_p": "p.R294X", "variant_type": "nonsense", "clinical_significance": "pathogenic"}],
    }
    unified = unify_entry(_entry("rett", "rett_001", gold_source="article"), expected, _ctx())
    entities = unified["expected_entities"]
    assert entities["gene"] == {"text": "MECP2", "hgnc_id": "HGNC:6992"}
    assert entities["disease"] == {"text": "Rett syndrome", "mondo_id": "MONDO:0010726"}
    assert entities["variants"][0]["text"] == "p.R294X"
    assert unified["backfilled"]["expected_entities"] == "derived_from_standardization"


# ---------------------------------------------------------------------------
# evaluation_config generation
# ---------------------------------------------------------------------------


def test_evaluation_config_generated_from_evidence_field_ids() -> None:
    expected = {
        "entry_id": "parkinson_000",
        "gene_symbol": "PRKN",
        "hgnc_id": "HGNC:8607",
        "disease_label": "Parkinson disease",
        "mondo_id": "MONDO:0005180",
        "moi": "AR",
        "source_pmid": "16227559",
        "expected_evidence": [
            {"field_id": "A.gene_symbol"},
            {"field_id": "B.disease_diagnosis"},
            {"field_id": "A.variant_hgvs_p"},
            {"field_id": "C.de_novo_status"},
            {"field_id": "B.hpo_terms"},
        ],
        "expected_standardization": {"gene": "HGNC:8607", "disease": "MONDO:0005180"},
        "expected_entities": {},
    }
    ctx = _ctx(hgnc_aliases={"PRKN": {"approved": "PRKN", "hgnc_id": "HGNC:8607", "aliases": [], "previous": []}})
    unified = unify_entry(_entry("parkinson", "parkinson_000"), expected, ctx)
    config = unified["evaluation_config"]
    assert "A.gene_symbol" in config["gene_disease_fields"]
    assert "B.disease_diagnosis" in config["gene_disease_fields"]
    assert "A.variant_hgvs_p" in config["variant_fields"]
    assert "C.de_novo_status" in config["clinical_fields"]
    assert "B.hpo_terms" in config["clinical_fields"]
    assert config["standardization_fields"] == ["gene", "disease"]
    assert unified["backfilled"]["evaluation_config"] == "derived_from_evidence"


# ---------------------------------------------------------------------------
# EuropePMC cache-driven back-fill
# ---------------------------------------------------------------------------


def test_europepmc_backfill_from_cache() -> None:
    expected = {
        "entry_id": "clingen_000",
        "gene_symbol": "AARS1",
        "hgnc_id": "HGNC:20",
        "disease_label": "CMT2N",
        "mondo_id": "MONDO:0013212",
        "moi": "AD",
        "source_pmid": "41743127",
        # no doi / journal / year in original
        "expected_evidence": [{"field_id": "A.gene_symbol"}],
        "expected_standardization": {"gene": "HGNC:20", "disease": "MONDO:0013212"},
        "expected_entities": {},
    }
    ctx = _ctx(
        pmid_cache={
            "41743127": {
                "source_doi": "10.1/clingen",
                "source_journal": "Some Journal",
                "source_year": "2026",
            }
        }
    )
    unified = unify_entry(_entry("clingen", "clingen_000"), expected, ctx)
    assert unified["source_doi"] == "10.1/clingen"
    assert unified["source_journal"] == "Some Journal"
    assert unified["source_year"] == "2026"
    assert unified["backfilled"]["source_doi"] == "europepmc_pmid"
    assert unified["backfilled"]["source_journal"] == "europepmc_pmid"
    assert unified["backfilled"]["source_year"] == "europepmc_pmid"


# ---------------------------------------------------------------------------
# PDF path resolution
# ---------------------------------------------------------------------------


def test_pdf_path_resolve_parkinson_meta_and_clingen_pipeline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(bud, "BENCHMARK_ROOT", tmp_path)
    monkeypatch.setattr(bud, "PIPELINE_PDF_ROOT", tmp_path / "pipeline" / "input" / "ground_truth")
    # parkinson meta pdf
    meta_dir = tmp_path / "data" / "ground_truth" / "parkinson" / "parkinson_000"
    meta_dir.mkdir(parents=True)
    pdf = tmp_path / "data" / "processed" / "parkinson" / "pdfs" / "16227559.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"%PDF-1.4")
    (meta_dir / "meta.json").write_text(json.dumps({"pdf_path": str(pdf)}), encoding="utf-8")
    expected_p = {
        "entry_id": "parkinson_000",
        "gene_symbol": "PRKN",
        "hgnc_id": "HGNC:8607",
        "disease_label": "Parkinson disease",
        "mondo_id": "MONDO:0005180",
        "moi": "AR",
        "source_pmid": "16227559",
        "expected_evidence": [{"field_id": "A.gene_symbol"}],
        "expected_standardization": {"gene": "HGNC:8607", "disease": "MONDO:0005180"},
        "expected_entities": {},
    }
    ctx = _ctx(hgnc_aliases={"PRKN": {"approved": "PRKN", "hgnc_id": "HGNC:8607", "aliases": [], "previous": []}})
    unified_p = unify_entry(_entry("parkinson", "parkinson_000"), expected_p, ctx)
    assert unified_p["source_pdf_path"].endswith("16227559.pdf")

    # clingen pipeline pdf (English)
    clin_pdf_dir = tmp_path / "pipeline" / "input" / "ground_truth" / "en" / "case_report"
    clin_pdf_dir.mkdir(parents=True)
    (clin_pdf_dir / "clingen_000.pdf").write_bytes(b"%PDF-1.4")
    expected_c = {
        "entry_id": "clingen_000",
        "gene_symbol": "AARS1",
        "hgnc_id": "HGNC:20",
        "disease_label": "CMT2N",
        "mondo_id": "MONDO:0013212",
        "moi": "AD",
        "source_pmid": "41743127",
        "expected_evidence": [{"field_id": "A.gene_symbol"}],
        "expected_standardization": {"gene": "HGNC:20", "disease": "MONDO:0013212"},
        "expected_entities": {},
    }
    unified_c = unify_entry(_entry("clingen", "clingen_000"), expected_c, _ctx())
    assert unified_c["source_pdf_path"].endswith("clingen_000.pdf")


def test_copy_pdf_files_materializes_multilingual_self_contained(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """All available language PDFs are copied in; primary -> source.pdf."""
    monkeypatch.setattr(bud, "BENCHMARK_ROOT", tmp_path)
    monkeypatch.setattr(bud, "PIPELINE_PDF_ROOT", tmp_path / "pipeline" / "input" / "ground_truth")
    pipe = tmp_path / "pipeline" / "input" / "ground_truth"
    for lang in ("en", "zh", "ja"):
        d = pipe / lang / "case_report"
        d.mkdir(parents=True)
        (d / "clingen_000.pdf").write_bytes(f"%PDF-{lang}".encode())
    dest = tmp_path / "out" / "gs_000"
    dest.mkdir(parents=True)
    entry = _entry("clingen", "clingen_000")
    files, primary_local = bud._copy_pdf_files(entry, {}, dest, "en")
    assert "source.pdf" in files
    assert "source_zh.pdf" in files
    assert "source_ja.pdf" in files
    assert (dest / "source.pdf").exists()
    assert (dest / "source_zh.pdf").exists()
    assert (dest / "source_ja.pdf").exists()


def test_copy_pdf_files_single_primary_for_parkinson(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Parkinson has a single PDF in meta.json; it becomes source.pdf."""
    monkeypatch.setattr(bud, "BENCHMARK_ROOT", tmp_path)
    meta_dir = tmp_path / "data" / "ground_truth" / "parkinson" / "parkinson_000"
    meta_dir.mkdir(parents=True)
    pdf = tmp_path / "data" / "processed" / "parkinson" / "16227559.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"%PDF-parkinson")
    (meta_dir / "meta.json").write_text(json.dumps({"pdf_path": str(pdf)}), encoding="utf-8")
    dest = tmp_path / "out" / "gs_081"
    dest.mkdir(parents=True)
    entry = _entry("parkinson", "parkinson_000")
    files, primary_local = bud._copy_pdf_files(entry, {}, dest, "en")
    assert files == ["source.pdf"]
    assert (dest / "source.pdf").read_bytes() == b"%PDF-parkinson"
    assert primary_local.endswith("source.pdf")
