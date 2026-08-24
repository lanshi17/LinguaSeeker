"""Tests for Stage-0c catalog field-item increment coverage."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from pydantic import ValidationError

from benchmark.experiments.acmg_multilingual.cli import _parse_args
from benchmark.experiments.acmg_multilingual.coverage import CoverageSpan
from benchmark.experiments.acmg_multilingual.evidence_item_coverage import (
    ALLOWED_FIELD_IDS,
    EvidenceItemSource,
    EvidenceItemCoverageTable,
    LayerField,
    load_evidence_item_coverage_table,
    summarize_evidence_item_coverage,
    verify_evidence_item_coverage,
)


def _repository_root() -> Path:
    """Return the monorepo root that contains benchmark/ and backend/."""
    return Path(__file__).resolve().parents[4]


def _span(line: int, quote: str, language: str = "en") -> CoverageSpan:
    """Build one line-anchored quote."""
    return CoverageSpan(line=line, quote=quote, language=language)


def _field(field_id: str, line: int, quote: str, language: str = "en") -> LayerField:
    """Build one catalog field anchored to a quote."""
    return LayerField(field_id=field_id, span=_span(line, quote, language))


def _source(**overrides: object) -> EvidenceItemSource:
    """Minimal bilingual source; callers override the fields under test."""
    payload: dict[str, object] = {
        "case_id": "case_x",
        "source_cluster_id": "case_x",
        "native_language": "zh",
        "increment_kind": "same_pdf_bilingual",
        "source_relative_path": "case_x/source.md",
        "source_sha256": "a" * 64,
        "english_abstract": (_field("B.disease_diagnosis", 1, "Rett"),),
        "english_visible": (_field("B.disease_diagnosis", 1, "Rett"),),
        "native_fulltext": (
            _field("B.disease_diagnosis", 1, "Rett"),
            _field("C.de_novo_status", 2, "de novo", "zh"),
        ),
        "increment_over_abstract": ("C.de_novo_status",),
        "increment_over_english_visible": ("C.de_novo_status",),
        "notes": "fixture",
    }
    payload.update(overrides)
    return EvidenceItemSource.model_validate(payload)


def test_allowed_field_ids_exist_in_product_catalog() -> None:
    """Increment ledger field_ids must remain a subset of the live catalog."""
    from src.core.evidence_extraction.domain.catalog import EVIDENCE_FIELD_SPECS

    catalog_ids = {spec.field_id for spec in EVIDENCE_FIELD_SPECS}
    assert ALLOWED_FIELD_IDS <= catalog_ids


def test_frozen_table_matches_on_disk_sources() -> None:
    """Committed quotes and hashes still match reviewed source.md files."""
    repository_root = _repository_root()
    table = load_evidence_item_coverage_table()
    summary = summarize_evidence_item_coverage(table)
    report = verify_evidence_item_coverage(
        table,
        reviewed_root=repository_root / "benchmark/experiments/acmg_multilingual/reviewed",
    )
    assert report.missed_spans == ()
    assert report.verified_sources == report.total_sources == 17
    assert report.verified_spans == report.total_spans
    assert summary.total_sources == 17
    assert summary.languages == ("es", "fr", "ja", "ko", "pt", "ru", "tr", "zh")
    assert summary.sources_with_abstract_increment == 12
    assert summary.sources_with_visible_increment == 12
    assert summary.abstract_increment_without_rett_007 == 11
    assert summary.same_pdf_bilingual_sources == 7
    assert summary.missing_english_pivot_sources == 5


def test_english_visible_must_contain_abstract_fields() -> None:
    """A visibility layer cannot drop a field the English abstract already has."""
    with pytest.raises(ValidationError, match="english_visible must contain english_abstract"):
        _source(
            english_visible=(_field("A.gene_symbol", 1, "MECP2"),),
            native_fulltext=(
                _field("A.gene_symbol", 1, "MECP2"),
                _field("B.disease_diagnosis", 1, "Rett"),
            ),
            increment_over_abstract=("A.gene_symbol",),
            increment_over_english_visible=("B.disease_diagnosis",),
        )


def test_increment_must_equal_set_difference() -> None:
    """Frozen increment lists are derived, not independently editable."""
    with pytest.raises(ValidationError, match="increment_over_abstract"):
        _source(increment_over_abstract=())


def test_kind_none_forbids_abstract_increment() -> None:
    """Negative-control papers cannot keep a nonempty increment list."""
    with pytest.raises(ValidationError, match="increment_kind=none"):
        _source(increment_kind="none")


def test_duplicate_field_id_in_one_layer_is_rejected() -> None:
    """A layer records presence once per catalog field."""
    with pytest.raises(ValidationError, match="duplicate field_id"):
        _source(
            english_abstract=(
                _field("B.disease_diagnosis", 1, "Rett"),
                _field("B.disease_diagnosis", 1, "RTT"),
            ),
        )


def test_verifier_reports_missing_span(tmp_path: Path) -> None:
    """A cited quote absent from its line is reported, not silently ignored."""
    source_text = "Rett syndrome\n父母未携带该变异位点\n"
    relative = Path("case_x/source.md")
    (tmp_path / relative).parent.mkdir(parents=True)
    (tmp_path / relative).write_text(source_text, encoding="utf-8")
    digest = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
    table = EvidenceItemCoverageTable(
        study_id="stage0c-test",
        protocol_version="v1",
        created_on="2026-08-20",
        scope_note="fixture",
        sources=(
            _source(
                source_sha256=digest,
                native_fulltext=(
                    _field("B.disease_diagnosis", 1, "Rett"),
                    _field("C.de_novo_status", 2, "父母均携带该变异位点", "zh"),
                ),
            ),
        ),
    )
    report = verify_evidence_item_coverage(table, tmp_path)
    assert report.verified_sources == 0
    assert "case_x:native_fulltext:C.de_novo_status:2" in report.missed_spans


def test_cli_check_evidence_item_coverage_parses_roots() -> None:
    """The Stage-0c audit keeps the fact table and reviewed root separate."""
    args = _parse_args(
        (
            "check-evidence-item-coverage",
            "--facts",
            "facts.json",
            "--reviewed-root",
            "reviewed",
            "--report",
            "report.json",
        )
    )
    assert args.facts == Path("facts.json")
    assert args.reviewed_root == Path("reviewed")
    assert args.report == Path("report.json")
