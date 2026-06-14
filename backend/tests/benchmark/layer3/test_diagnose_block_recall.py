"""Tests for block-level recall diagnostics."""
from __future__ import annotations

import json
from pathlib import Path

from benchmark.layer3.analysis.diagnose_block_recall import (
    build_block_recall_diagnostics,
    diagnostics_to_payload,
)


def _write_report(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "strategies": [
                    {
                        "strategy": "source_grounded_reconcile",
                        "per_entry": [
                            {
                                "entry_id": "clingen_000",
                                "gene_symbol": "GENE1",
                                "classification": "Limited",
                                "moi": "AD",
                                "field_matches": [
                                    {
                                        "field_id": "A.gene_disease_relationship",
                                        "expected": "causative",
                                        "matched": False,
                                        "extracted": None,
                                        "match_type": "missing",
                                        "source_span": None,
                                        "extra_found_values": [],
                                    }
                                ],
                            },
                            {
                                "entry_id": "clingen_001",
                                "gene_symbol": "GENE2",
                                "classification": "Definitive",
                                "moi": "AR",
                                "field_matches": [
                                    {
                                        "field_id": "B.disease_diagnosis",
                                        "expected": "rare disease",
                                        "matched": False,
                                        "extracted": None,
                                        "match_type": "missing",
                                        "source_span": None,
                                        "extra_found_values": [],
                                    }
                                ],
                            },
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_ground_truth(root: Path) -> None:
    entry0 = root / "clingen_000"
    entry0.mkdir(parents=True)
    (entry0 / "expected.json").write_text(
        json.dumps(
            {
                "entry_id": "clingen_000",
                "gene_symbol": "GENE1",
                "disease_label": "target disease",
                "moi": "AD",
            }
        ),
        encoding="utf-8",
    )
    (entry0 / "source.md").write_text(
        "The GENE1 pathogenic variant causes target disease in affected families.",
        encoding="utf-8",
    )

    entry1 = root / "clingen_001"
    entry1.mkdir(parents=True)
    (entry1 / "expected.json").write_text(
        json.dumps(
            {
                "entry_id": "clingen_001",
                "gene_symbol": "GENE2",
                "disease_label": "rare disease",
                "moi": "AR",
            }
        ),
        encoding="utf-8",
    )
    (entry1 / "source.md").write_text(
        "Table 1\n| Gene | Diagnosis |\n| GENE2 | rare disease |",
        encoding="utf-8",
    )


def test_build_block_recall_diagnostics_detects_source_cues_and_table_misses(tmp_path: Path) -> None:
    report_path = _write_report(tmp_path / "ablation.json")
    gt_root = tmp_path / "ground_truth"
    _write_ground_truth(gt_root)

    diagnostics = build_block_recall_diagnostics(report_path, ground_truth_dir=gt_root)

    assert len(diagnostics.rows) == 2
    by_entry = {row.entry_id: row for row in diagnostics.rows}
    assert by_entry["clingen_000"].source_contains_gene
    assert by_entry["clingen_000"].source_contains_disease
    assert by_entry["clingen_000"].source_contains_relationship_cue
    assert by_entry["clingen_000"].likely_generation_missing
    assert by_entry["clingen_001"].likely_table_related


def test_block_recall_payload_summarizes_generation_and_table_misses(tmp_path: Path) -> None:
    report_path = _write_report(tmp_path / "ablation.json")
    gt_root = tmp_path / "ground_truth"
    _write_ground_truth(gt_root)

    payload = diagnostics_to_payload(
        build_block_recall_diagnostics(report_path, ground_truth_dir=gt_root)
    )

    assert payload["summary"]["total_missing_fields"] == 2
    assert payload["summary"]["likely_generation_missing"] == 2
    assert payload["summary"]["likely_table_related"] == 1
    assert payload["summary"]["by_field"]["A.gene_disease_relationship"] == 1
