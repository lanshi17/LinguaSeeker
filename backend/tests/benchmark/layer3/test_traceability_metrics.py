"""Tests for formal traceability metrics."""
from __future__ import annotations

import json
from pathlib import Path

from benchmark.analysis.traceability.metrics import (
    build_traceability_report,
    span_boundary_f1,
    traceable_f1,
)


def _write_source(root: Path, entry_id: str, text: str) -> None:
    entry_dir = root / entry_id
    entry_dir.mkdir(parents=True)
    (entry_dir / "source.md").write_text(text, encoding="utf-8")


def _field_match(
    *,
    text: str,
    start: int,
    end: int,
    matched: bool = True,
) -> dict[str, object]:
    return {
        "field_id": "A.gene_symbol",
        "expected": "GENE1",
        "extracted": "GENE1",
        "matched": matched,
        "match_type": "exact" if matched else "wrong_value",
        "source_span": {
            "span_id": "original-p1",
            "start_offset": start,
            "end_offset": end,
            "text_snippet": text,
        },
        "gold_source_span": {
            "start_offset": 0,
            "end_offset": 33,
            "text_snippet": "GENE1 causes the target disease.",
        },
        "extra_found_values": [],
    }


def _write_system_report(path: Path, field_matches: list[dict[str, object]]) -> None:
    path.write_text(
        json.dumps(
            {
                "strategies": [
                    {
                        "strategy": "context_verifier_reconcile",
                        "total_entries": 1,
                        "aggregates": {"overall": {"precision": 1.0, "recall": 1.0, "f1": 1.0}},
                        "per_entry": [
                            {
                                "entry_id": "clingen_000",
                                "field_matches": field_matches,
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


def test_citation_validity_counts_span_id_backed_source(tmp_path: Path) -> None:
    ground_truth_root = tmp_path / "ground_truth"
    source_text = "GENE1 causes the target disease. Extra context."
    _write_source(ground_truth_root, "clingen_000", source_text)
    report_path = tmp_path / "reconcile_ablation.json"
    _write_system_report(report_path, [_field_match(text=source_text[0:33], start=0, end=33)])

    report = build_traceability_report(
        system_report_path=report_path,
        strategy="context_verifier_reconcile",
        ground_truth_root=ground_truth_root,
    )

    assert report.overall.citation_validity_rate == 1.0
    assert report.overall.hallucinated_citation_rate == 0.0
    assert report.counts.citation_valid == 1


def test_hallucinated_citation_counts_missing_source_text(tmp_path: Path) -> None:
    ground_truth_root = tmp_path / "ground_truth"
    _write_source(ground_truth_root, "clingen_000", "GENE1 causes the target disease.")
    report_path = tmp_path / "reconcile_ablation.json"
    _write_system_report(report_path, [_field_match(text="Not in the source.", start=90, end=108)])

    report = build_traceability_report(
        system_report_path=report_path,
        strategy="context_verifier_reconcile",
        ground_truth_root=ground_truth_root,
    )

    assert report.overall.citation_validity_rate == 0.0
    assert report.overall.hallucinated_citation_rate == 1.0
    assert report.counts.hallucinated == 1


def test_citation_validity_accepts_recoverable_token_sequence_when_offsets_drift(tmp_path: Path) -> None:
    ground_truth_root = tmp_path / "ground_truth"
    _write_source(
        ground_truth_root,
        "clingen_000",
        "Genetic testing confirmed the diagnosis of X-ALD resulting from novel ATP-binding cassette transports.",
    )
    report_path = tmp_path / "reconcile_ablation.json"
    _write_system_report(
        report_path,
        [
            _field_match(
                text="Genetic testing confirmed the diagnosis of X-ALD resulting from a novel ATP binding cassette transports.",
                start=100,
                end=198,
            )
        ],
    )

    report = build_traceability_report(
        system_report_path=report_path,
        strategy="context_verifier_reconcile",
        ground_truth_root=ground_truth_root,
    )

    assert report.overall.citation_validity_rate == 1.0
    assert report.overall.hallucinated_citation_rate == 0.0


def test_span_boundary_f1_uses_token_overlap() -> None:
    predicted = "GENE1 causes target disease"
    gold = "GENE1 causes the target disease"

    assert span_boundary_f1(predicted, gold) == 0.8889


def test_traceable_f1_multiplies_extraction_f1_by_cvr() -> None:
    assert traceable_f1(extraction_f1=0.8, citation_validity_rate=0.5) == 0.4


def test_cross_lingual_consistency_uses_original_translated_field_agreement(tmp_path: Path) -> None:
    ground_truth_root = tmp_path / "ground_truth"
    entry_dir = ground_truth_root / "clingen_000"
    preprocessed_dir = entry_dir / "preprocessed" / "phase_2"
    preprocessed_dir.mkdir(parents=True)
    (entry_dir / "source.md").write_text("GENE1 causes the target disease.", encoding="utf-8")
    (preprocessed_dir / "extraction_result.json").write_text(
        json.dumps(
            {
                "original_result": {
                    "evidence_items": [
                        {"field_id": "A.gene_symbol", "value": "GENE1"},
                        {"field_id": "B.disease_diagnosis", "value": "Disease A"},
                    ]
                },
                "translated_result": {
                    "evidence_items": [
                        {"field_id": "A.gene_symbol", "value": "GENE1"},
                        {"field_id": "B.disease_diagnosis", "value": "Disease B"},
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    report_path = tmp_path / "reconcile_ablation.json"
    _write_system_report(report_path, [_field_match(text="GENE1 causes the target disease.", start=0, end=33)])

    report = build_traceability_report(
        system_report_path=report_path,
        strategy="context_verifier_reconcile",
        ground_truth_root=ground_truth_root,
    )

    assert report.overall.cross_lingual_consistency == 0.5


def test_cross_lingual_consistency_handles_field_present_in_one_track_only(tmp_path: Path) -> None:
    ground_truth_root = tmp_path / "ground_truth"
    entry_dir = ground_truth_root / "clingen_000"
    preprocessed_dir = entry_dir / "preprocessed" / "phase_2"
    preprocessed_dir.mkdir(parents=True)
    (entry_dir / "source.md").write_text("GENE1 causes the target disease.", encoding="utf-8")
    (preprocessed_dir / "extraction_result.json").write_text(
        json.dumps(
            {
                "original_result": {"evidence_items": [{"field_id": "A.gene_symbol", "value": "GENE1"}]},
                "translated_result": {
                    "evidence_items": [
                        {"field_id": "A.gene_symbol", "value": "GENE1"},
                        {"field_id": "B.disease_diagnosis", "value": "Disease A"},
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    report_path = tmp_path / "reconcile_ablation.json"
    _write_system_report(report_path, [_field_match(text="GENE1 causes the target disease.", start=0, end=33)])

    report = build_traceability_report(
        system_report_path=report_path,
        strategy="context_verifier_reconcile",
        ground_truth_root=ground_truth_root,
    )

    assert report.overall.cross_lingual_consistency == 0.5
