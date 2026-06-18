"""Tests for offline reconcile oracle upper-bound diagnostics."""
from __future__ import annotations

import json
from pathlib import Path

from benchmark.analysis.reconcile.oracle_upper_bound import (
    OracleStrategy,
    build_oracle_items,
    run_oracle_upper_bound,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    DualEvidenceExtractionResult,
    EvidenceExtractionResult,
    EvidenceExtractionStatus,
    EvidenceItem,
    EvidenceStatus,
    Track,
)


def _item(field_id: str, value: str) -> EvidenceItem:
    return EvidenceItem(
        field_id=field_id,
        category=field_id.split(".", maxsplit=1)[0],
        field_name=field_id,
        status=EvidenceStatus.FOUND,
        value=value,
        confidence=0.8,
    )


def _non_scorable_item(field_id: str, value: str) -> EvidenceItem:
    return EvidenceItem(
        field_id=field_id,
        category=field_id.split(".", maxsplit=1)[0],
        field_name=field_id,
        status=EvidenceStatus.SOURCE_INVALID,
        value=value,
        confidence=0.8,
    )


def _result(track: Track, items: list[EvidenceItem]) -> EvidenceExtractionResult:
    return EvidenceExtractionResult(
        status=EvidenceExtractionStatus.COMPLETED,
        document_id="doc",
        track=track,
        evidence_items=items,
    )


def _dual_result() -> DualEvidenceExtractionResult:
    return DualEvidenceExtractionResult(
        document_id="doc",
        original_result=_result(
            Track.ORIGINAL,
            [
                _item("A.gene_symbol", "GENE1"),
                _item("B.disease_diagnosis", "wrong disease"),
                _item("A.gene_disease_relationship", "associated"),
            ],
        ),
        translated_result=_result(
            Track.TRANSLATED,
            [
                _item("A.gene_symbol", "GENE1"),
                _item("B.disease_diagnosis", "target disease"),
                _item("A.gene_disease_relationship", "causative"),
            ],
        ),
    )


def test_oracle_best_dual_candidate_picks_matching_candidates() -> None:
    expected_fields = [
        {"field_id": "A.gene_symbol", "value": "GENE1"},
        {"field_id": "B.disease_diagnosis", "value": "target disease"},
        {"field_id": "A.gene_disease_relationship", "value": "causative"},
    ]

    items = build_oracle_items(
        _dual_result(),
        expected_fields,
        OracleStrategy.ORACLE_BEST_DUAL_CANDIDATE,
    )

    by_field = {str(item["field_id"]): item for item in items}
    assert by_field["A.gene_symbol"]["value"] == "GENE1"
    assert by_field["B.disease_diagnosis"]["value"] == "target disease"
    assert by_field["A.gene_disease_relationship"]["value"] == "causative"


def test_oracle_best_dual_candidate_skips_non_scorable_matching_candidate() -> None:
    result = DualEvidenceExtractionResult(
        document_id="doc",
        original_result=_result(
            Track.ORIGINAL,
            [
                _non_scorable_item("A.gene_symbol", "GENE1"),
                _item("A.gene_symbol", "GENE1"),
            ],
        ),
        translated_result=_result(Track.TRANSLATED, []),
    )

    items = build_oracle_items(
        result,
        [{"field_id": "A.gene_symbol", "value": "GENE1"}],
        OracleStrategy.ORACLE_BEST_DUAL_CANDIDATE,
    )

    assert items[0]["status"] == "found"
    assert items[0]["value"] == "GENE1"


def test_oracle_relationship_only_changes_only_relationship_field() -> None:
    expected_fields = [
        {"field_id": "B.disease_diagnosis", "value": "target disease"},
        {"field_id": "A.gene_disease_relationship", "value": "causative"},
    ]

    items = build_oracle_items(
        _dual_result(),
        expected_fields,
        OracleStrategy.ORACLE_RELATIONSHIP_ONLY,
    )

    by_field = {str(item["field_id"]): item for item in items}
    assert by_field["B.disease_diagnosis"]["value"] == "wrong disease"
    assert by_field["A.gene_disease_relationship"]["value"] == "causative"


def test_run_oracle_upper_bound_reports_multiple_strategies(tmp_path: Path) -> None:
    entry_id = "clingen_test"
    artifact_dir = tmp_path / entry_id / "preprocessed" / "phase_2"
    artifact_dir.mkdir(parents=True)
    (tmp_path / "selection.json").write_text(
        json.dumps(
            [
                {
                    "entry_id": entry_id,
                    "gene_symbol": "GENE1",
                    "disease_label": "target disease",
                    "classification": "Limited",
                    "moi": "AD",
                }
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / entry_id / "expected.json").write_text(
        json.dumps(
            {
                "expected_evidence": [
                    {"field_id": "A.gene_symbol", "value": "GENE1"},
                    {"field_id": "B.disease_diagnosis", "value": "target disease"},
                    {"field_id": "A.gene_disease_relationship", "value": "causative"},
                ]
            }
        ),
        encoding="utf-8",
    )
    (artifact_dir / "extraction_result.json").write_text(
        _dual_result().model_dump_json(),
        encoding="utf-8",
    )

    report = run_oracle_upper_bound(
        ground_truth_dir=tmp_path,
        reports_dir=tmp_path / "reports",
        save_report=False,
    )

    by_strategy = {strategy.strategy: strategy for strategy in report.strategies}
    assert by_strategy[OracleStrategy.ORACLE_BEST_DUAL_CANDIDATE].aggregates["overall"]["f1"] == 1.0
    assert by_strategy[OracleStrategy.ORACLE_RELATIONSHIP_ONLY].aggregates["overall"]["f1"] < 1.0
    assert by_strategy[OracleStrategy.ORACLE_NO_OVER_EXTRACTIONS].total_entries == 1
