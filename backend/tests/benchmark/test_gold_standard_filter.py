"""Tests for the gold-standard literature filter gate logic.

Covers each gate in isolation with synthetic ``EntryRecord`` fixtures plus an
end-to-end selection assembly check. Filesystem-dependent behaviour (PDF
relocation) uses a monkeypatched ``RAW_PDF_ROOT`` so the real benchmark tree is
never touched.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from benchmark.analysis.dataset_curation import gold_standard_filter as gsf
from benchmark.analysis.dataset_curation.gold_standard_filter import (
    EntryRecord,
    build_gold_standard_selection,
    compute_dedup,
    gate_article_alignment,
    gate_source_integrity,
    gate_standardization_ids,
    gate_verifiable_source,
)
from benchmark.core.paths import BENCHMARK_ROOT


def _record(
    *,
    entry_id: str = "test_000",
    dataset: str = "clingen",
    expected: dict[str, object] | None = None,
    source_md: str = "# A Real Article Title About CFTR\n\n" + "Body text. " * 300,
    entry_dir: Path | None = None,
) -> EntryRecord:
    return EntryRecord(
        entry_id=entry_id,
        source_dataset=dataset,
        entry_dir=entry_dir or BENCHMARK_ROOT / "data" / "ground_truth" / dataset / entry_id,
        expected=expected or {"gene_symbol": "CFTR", "disease_label": "cystic fibrosis"},
        meta={},
        source_md=source_md,
        source_md_path=Path("source.md"),
    )


# ---------------------------------------------------------------------------
# Gate 1: source integrity
# ---------------------------------------------------------------------------


def test_source_integrity_rejects_erratum() -> None:
    record = _record(source_md="# Erratum in: Earlier Article\n\nCorrection notice text.")
    result = gate_source_integrity(record)
    assert not result.passed
    assert result.detail["detected_kind"] == "erratum"


def test_source_integrity_rejects_multi_article_corpus() -> None:
    titles = "\n\n".join(
        f"# Study Number {i}: A Distinct Paper Title About Gene{i}\n\n"
        + "Substantial body text for this article. " * 40
        for i in range(5)
    )
    record = _record(source_md=titles)
    result = gate_source_integrity(record)
    assert not result.passed
    assert result.detail["detected_kind"] == "multi_article_corpus"


def test_source_integrity_accepts_split_title_under_threshold() -> None:
    md = (
        "# RETT SENDROMLU HASTALARIN VE\n"
        "# KLINIK VE MOLEKULER DEGERLENDIRMESI\n"
        "# GENOTIP FENOTIP KORELASYONUNUN ARASTIRILMASI\n\n" + "Turkish body text. " * 300
    )
    record = _record(source_md=md)
    result = gate_source_integrity(record)
    assert result.passed
    assert result.detail["detected_kind"] == "single_article"


def test_source_integrity_rejects_parse_fragment() -> None:
    record = _record(source_md="# Short\n\ntiny.")
    result = gate_source_integrity(record)
    assert not result.passed
    assert result.detail["detected_kind"] == "fragment"


# ---------------------------------------------------------------------------
# Gate 2: standardization IDs
# ---------------------------------------------------------------------------


def test_standardization_passes_with_valid_ids() -> None:
    record = _record(
        expected={
            "gene_symbol": "CFTR",
            "expected_standardization": {"gene": "HGNC:1884", "disease": "MONDO:0009061"},
        }
    )
    result = gate_standardization_ids(record, alias_map={})
    assert result.passed
    assert result.detail["gene_id"] == "HGNC:1884"


def test_standardization_backfills_parkinson_bare_symbol() -> None:
    record = _record(
        dataset="parkinson",
        expected={
            "gene_symbol": "PRKN",
            "expected_standardization": {"gene": "PRKN", "disease": "MONDO:0005180"},
        },
    )
    alias_map = {"PRKN": {"approved": "PRKN", "hgnc_id": "HGNC:8607", "aliases": [], "previous": ["PARK2"]}}
    result = gate_standardization_ids(record, alias_map)
    assert result.passed
    assert result.detail["backfilled_hgnc_id"] == "HGNC:8607"


def test_standardization_fails_without_resolvable_gene() -> None:
    record = _record(
        expected={
            "gene_symbol": "UNKNOWN",
            "expected_standardization": {"gene": "UNKNOWN", "disease": "MONDO:0005180"},
        }
    )
    result = gate_standardization_ids(record, alias_map={})
    assert not result.passed


# ---------------------------------------------------------------------------
# Gate 3: article-evidence alignment
# ---------------------------------------------------------------------------


def test_alignment_passes_when_gene_present() -> None:
    record = _record(
        source_md="# Title\n\nThe CFTR gene was sequenced in all patients.",
        expected={"gene_symbol": "CFTR", "disease_label": "cystic fibrosis"},
    )
    result = gate_article_alignment(record, alias_map={})
    assert result.passed
    assert result.detail["gene_matched_via"] == "CFTR"


def test_alignment_fails_when_gene_absent() -> None:
    record = _record(
        source_md="# Title\n\nAn unrelated study about a different gene entirely.",
        expected={"gene_symbol": "CFTR", "disease_label": "cystic fibrosis"},
    )
    result = gate_article_alignment(record, alias_map={})
    assert not result.passed


def test_alignment_matches_via_previous_symbol() -> None:
    # PRKN is frequently referred to as "parkin" / PARK2 in literature.
    record = _record(
        source_md="# Title\n\nWe screened the parkin gene for mutations.",
        expected={"gene_symbol": "PRKN", "disease_label": "Parkinson disease"},
    )
    alias_map = {
        "PRKN": {
            "approved": "PRKN",
            "hgnc_id": "HGNC:8607",
            "aliases": ["PDJ", "AR-JP", "parkin"],
            "previous": ["PARK2"],
        }
    }
    result = gate_article_alignment(record, alias_map)
    assert result.passed
    assert result.detail["gene_matched_via"] == "parkin"


# ---------------------------------------------------------------------------
# Gate 4: verifiable source
# ---------------------------------------------------------------------------


def test_verifiable_source_passes_via_doi() -> None:
    record = _record(expected={"gene_symbol": "CFTR", "source_doi": "10.1234/test"})
    assert gate_verifiable_source(record).passed


def test_verifiable_source_fails_with_nothing() -> None:
    record = _record(expected={"gene_symbol": "CFTR"})
    assert not gate_verifiable_source(record).passed


def test_verifiable_source_resolves_relocated_pdf(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    relocated = tmp_path / "downloads"
    (relocated / "rett" / "de").mkdir(parents=True)
    pdf = relocated / "rett" / "de" / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    monkeypatch.setattr(gsf, "RAW_PDF_ROOT", relocated)
    record = _record(
        dataset="rett",
        expected={
            "gene_symbol": "MECP2",
            "source_pdf_path": "/old/legacy/path/downloads/rett/de/paper.pdf",
        },
    )
    result = gate_verifiable_source(record)
    assert result.passed
    assert result.detail["local_pdf_exists"] is True
    assert result.detail["resolved_pdf_path"].endswith("paper.pdf")


# ---------------------------------------------------------------------------
# Gate 5: cross-dataset dedup
# ---------------------------------------------------------------------------


def test_dedup_keeps_richer_entry_across_datasets() -> None:
    base = {"source_pmid": "12345", "expected_evidence": [{"field_id": "A.gene_symbol"}]}
    rich = dict(base)
    rich["expected_evidence"] = [
        {"field_id": "A.gene_symbol"},
        {"field_id": "B.disease_diagnosis"},
        {"field_id": "A.variant_hgvs_p"},
    ]
    records = [
        _record(entry_id="db_a", dataset="clingen", expected=rich),
        _record(entry_id="art_b", dataset="rett", expected=base),
    ]
    results = compute_dedup(records)
    assert results["db_a"].passed  # richer + DB-grounded wins
    assert not results["art_b"].passed
    assert results["art_b"].detail["dedup_winner"] == "db_a"


def test_dedup_ignores_same_dataset_duplicates() -> None:
    records = [
        _record(entry_id="a1", dataset="clingen", expected={"source_pmid": "999"}),
        _record(entry_id="a2", dataset="clingen", expected={"source_pmid": "999"}),
    ]
    results = compute_dedup(records)
    assert results["a1"].passed
    assert results["a2"].passed


# ---------------------------------------------------------------------------
# End-to-end selection assembly
# ---------------------------------------------------------------------------


def test_build_selection_assigns_unified_ids_and_tags_gold_source(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Point HGNC + PDF roots away from the real tree.
    monkeypatch.setattr(gsf, "HGNC_TERMINOLOGY_FILE", tmp_path / "missing_hgnc.txt")
    monkeypatch.setattr(gsf, "RAW_PDF_ROOT", tmp_path / "downloads")
    alias_map = {
        "PRKN": {"approved": "PRKN", "hgnc_id": "HGNC:8607", "aliases": [], "previous": []},
    }
    records = [
        _record(
            entry_id="clingen_000",
            dataset="clingen",
            source_md="# AARS1 Study Title\n\nThe AARS1 gene causes CMT2N. " * 40,
            expected={
                "gene_symbol": "AARS1",
                "disease_label": "CMT2N",
                "expected_standardization": {"gene": "HGNC:20", "disease": "MONDO:0013212"},
                "expected_evidence": [{"field_id": "A.gene_symbol"}],
                "source_pmid": "111",
            },
        ),
        _record(
            entry_id="parkinson_000",
            dataset="parkinson",
            source_md="# PRKN Study Title\n\nThe PRKN gene in Parkinson disease. " * 40,
            expected={
                "gene_symbol": "PRKN",
                "disease_label": "Parkinson disease",
                "expected_standardization": {"gene": "PRKN", "disease": "MONDO:0005180"},
                "expected_evidence": [{"field_id": "A.gene_symbol"}, {"field_id": "B.disease_diagnosis"}],
                "source_doi": "10.1/x",
            },
        ),
    ]
    reports, selection, dedup = build_gold_standard_selection(records, alias_map)
    assert len(selection) == 2
    assert [e["unified_id"] for e in selection] == ["gs_000", "gs_001"]
    by_orig = {e["original_entry_id"]: e for e in selection}
    assert by_orig["clingen_000"]["gold_source"] == "database"
    assert by_orig["parkinson_000"]["gold_source"] == "article"
    assert by_orig["parkinson_000"]["hgnc_id"] == "HGNC:8607"
    assert by_orig["parkinson_000"]["backfilled"]["hgnc_id"] == "HGNC:8607"
    # The non-passing report carries no selection payload; here all pass.
    assert all(r["overall_passed"] for r in reports)
    assert dedup == []
