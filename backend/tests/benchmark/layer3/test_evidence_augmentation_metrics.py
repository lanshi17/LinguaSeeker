"""Tests for multilingual evidence augmentation metrics."""

from __future__ import annotations

import json
from pathlib import Path

from benchmark.analysis.dataset_curation.evidence_augmentation_metrics import (
    AugmentationMetricConfig,
    build_evidence_augmentation_report,
)


def _source(span_id: str, text: str) -> dict[str, object]:
    return {
        "span_id": span_id,
        "page": 1,
        "start_offset": 0,
        "end_offset": len(text),
        "context_type": "text",
        "context_ref": "Results",
        "text_snippet": text,
    }


def _item(
    *,
    field_id: str,
    value: str,
    language: str,
    source: dict[str, object] | None = None,
    acmg_codes: list[str] | None = None,
    notes: str = "",
) -> dict[str, object]:
    return {
        "field_id": field_id,
        "category": field_id.split(".", maxsplit=1)[0],
        "field_name": field_id,
        "status": "found",
        "value": value,
        "confidence": 0.9,
        "article_language": language,
        "evidence_source_language": language,
        "is_english": language == "en",
        "requires_translation": language != "en",
        "source": source,
        "assigned_acmg_codes": acmg_codes or [],
        "notes": notes,
    }


def _unknown_language_item(
    *,
    field_id: str,
    value: str,
) -> dict[str, object]:
    return {
        "field_id": field_id,
        "category": field_id.split(".", maxsplit=1)[0],
        "field_name": field_id,
        "status": "found",
        "value": value,
        "confidence": 0.9,
        "source": _source("unknown-source", f"{value} is reported."),
        "assigned_acmg_codes": [],
        "notes": "",
    }


def test_evidence_augmentation_matrix_counts_non_english_added_traceable_evidence(tmp_path: Path) -> None:
    entry_dir = tmp_path / "case_001"
    artifact_dir = entry_dir / "preprocessed" / "phase_2"
    artifact_dir.mkdir(parents=True)
    (tmp_path / "selection.json").write_text(
        json.dumps([{"entry_id": "case_001", "gene_symbol": "GENE1", "disease_label": "Disease A"}]),
        encoding="utf-8",
    )
    (artifact_dir / "extraction_result.json").write_text(
        json.dumps(
            {
                "document_id": "doc-1",
                "reconciled_result": {
                    "status": "completed",
                    "document_id": "doc-1",
                    "track": "reconciled",
                    "evidence_items": [
                        _item(
                            field_id="A.gene_symbol",
                            value="GENE1",
                            language="en",
                            source=_source("en-gene", "GENE1 is reported."),
                        ),
                        _item(
                            field_id="B.disease_diagnosis",
                            value="Disease A",
                            language="en",
                            source=_source("en-disease", "Disease A is reported."),
                        ),
                        _item(
                            field_id="A.gene_symbol",
                            value="GENE1",
                            language="zh",
                            source=_source("zh-gene", "GENE1 is reported in Chinese."),
                        ),
                        _item(
                            field_id="A.variant_hgvs_p",
                            value="p.Arg1His",
                            language="zh",
                            source=_source("zh-variant", "p.Arg1His is reported."),
                            acmg_codes=["PS3"],
                        ),
                        _item(
                            field_id="B.disease_diagnosis",
                            value="Disease B",
                            language="zh",
                            source=_source("zh-disease", "Disease B is reported."),
                            notes="manual review recommended for conflict",
                        ),
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    report = build_evidence_augmentation_report(AugmentationMetricConfig(ground_truth_root=tmp_path))

    matrix = report.per_case[0].matrix
    assert matrix.english_only_evidence_count == 2
    assert matrix.multilingual_evidence_count == 5
    assert matrix.non_english_added_evidence_count == 2
    assert matrix.duplicated_evidence_count == 1
    assert matrix.unknown_language_evidence_count == 0
    assert matrix.conflicting_evidence_count == 1
    assert matrix.traceable_added_evidence_count == 2
    assert matrix.potential_acmg_evidence_type_counts["PS3/BS3"] == 1
    assert report.overall.evidence_coverage_gain == 1.0
    assert report.overall.non_english_evidence_yield == 0.6
    assert report.overall.traceable_augmentation_rate == 1.0
    assert report.overall.reviewer_burden == 0.5


def test_evidence_augmentation_keeps_missing_language_out_of_non_english_yield(tmp_path: Path) -> None:
    entry_dir = tmp_path / "case_001"
    artifact_dir = entry_dir / "preprocessed" / "phase_2"
    artifact_dir.mkdir(parents=True)
    (tmp_path / "selection.json").write_text(json.dumps([{"entry_id": "case_001"}]), encoding="utf-8")
    (artifact_dir / "extraction_result.json").write_text(
        json.dumps(
            {
                "document_id": "doc-1",
                "reconciled_result": {
                    "status": "completed",
                    "document_id": "doc-1",
                    "track": "reconciled",
                    "evidence_items": [
                        _item(field_id="A.gene_symbol", value="GENE1", language="en"),
                        _unknown_language_item(field_id="A.variant_hgvs_p", value="p.Arg1His"),
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    report = build_evidence_augmentation_report(AugmentationMetricConfig(ground_truth_root=tmp_path))

    matrix = report.per_case[0].matrix
    assert matrix.english_only_evidence_count == 1
    assert matrix.multilingual_evidence_count == 2
    assert matrix.non_english_added_evidence_count == 0
    assert matrix.duplicated_evidence_count == 0
    assert matrix.unknown_language_evidence_count == 1
    assert report.overall.non_english_evidence_yield == 0.0
    assert matrix.conflicting_evidence_count == 0
    assert matrix.traceable_added_evidence_count == 0
    assert report.overall.evidence_coverage_gain == 0.0
    assert report.overall.traceable_augmentation_rate == 0.0
    assert report.overall.reviewer_burden == 0.0


def test_evidence_augmentation_uses_dual_track_union_when_reconciled_result_is_absent(tmp_path: Path) -> None:
    entry_dir = tmp_path / "case_001"
    artifact_dir = entry_dir / "preprocessed" / "phase_2"
    artifact_dir.mkdir(parents=True)
    (tmp_path / "selection.json").write_text(json.dumps([{"entry_id": "case_001"}]), encoding="utf-8")
    (artifact_dir / "extraction_result.json").write_text(
        json.dumps(
            {
                "document_id": "doc-1",
                "original_result": {
                    "status": "completed",
                    "document_id": "doc-1",
                    "track": "original",
                    "evidence_items": [
                        _item(field_id="A.gene_symbol", value="GENE1", language="ja"),
                    ],
                },
                "translated_result": {
                    "status": "completed",
                    "document_id": "doc-1",
                    "track": "translated",
                    "evidence_items": [
                        _item(field_id="A.gene_symbol", value="GENE1", language="en"),
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    report = build_evidence_augmentation_report(AugmentationMetricConfig(ground_truth_root=tmp_path))

    matrix = report.per_case[0].matrix
    assert matrix.english_only_evidence_count == 1
    assert matrix.multilingual_evidence_count == 2
    assert matrix.non_english_added_evidence_count == 0
    assert matrix.duplicated_evidence_count == 1
