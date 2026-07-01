"""Tests for Benchmark C expansion entry selection."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from benchmark.analysis.dataset_curation.select_expansion import (
    ExpansionSelectionConfig,
    build_expansion_selection,
    expansion_selection_to_payload,
    format_expansion_selection,
    write_expansion_selection,
)


def _write_core_selection(ground_truth_root: Path, core_rows: list[dict[str, str]]) -> Path:
    ground_truth_root.mkdir(parents=True, exist_ok=True)
    selection_path = ground_truth_root / "selection.json"
    selection_path.write_text(json.dumps(core_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return selection_path


def _write_csv(path: Path, rows: list[dict[str, str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "GENE SYMBOL",
                "GENE ID (HGNC)",
                "DISEASE LABEL",
                "DISEASE ID (MONDO)",
                "MOI",
                "SOP",
                "CLASSIFICATION",
                "ONLINE REPORT",
                "CLASSIFICATION DATE",
                "GCEP",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def test_expansion_selection_skips_frozen_core_and_is_deterministic(tmp_path: Path) -> None:
    ground_truth_root = tmp_path / "ground_truth"
    core_rows = [
        {
            "entry_id": "clingen_000",
            "clingen_report_url": "https://example.test/core-000",
            "gene_symbol": "GENE0",
            "disease_label": "core disease 0",
            "classification": "Definitive",
            "moi": "AD",
            "gcep": "GCEP-A",
        },
        {
            "entry_id": "clingen_001",
            "clingen_report_url": "https://example.test/core-001",
            "gene_symbol": "GENE1",
            "disease_label": "core disease 1",
            "classification": "Strong",
            "moi": "AR",
            "gcep": "GCEP-B",
        },
    ]
    _write_core_selection(ground_truth_root, core_rows)

    csv_path = _write_csv(
        tmp_path / "clingen.csv",
        [
            {
                "GENE SYMBOL": "GENE0",
                "GENE ID (HGNC)": "HGNC:0",
                "DISEASE LABEL": "core disease 0",
                "DISEASE ID (MONDO)": "MONDO:0",
                "MOI": "AD",
                "SOP": "SOP1",
                "CLASSIFICATION": "Definitive",
                "ONLINE REPORT": "https://example.test/core-000",
                "CLASSIFICATION DATE": "2024-01-01T00:00:00Z",
                "GCEP": "GCEP-A",
            },
            {
                "GENE SYMBOL": "GENE2",
                "GENE ID (HGNC)": "HGNC:2",
                "DISEASE LABEL": "disease two",
                "DISEASE ID (MONDO)": "MONDO:2",
                "MOI": "XL",
                "SOP": "SOP2",
                "CLASSIFICATION": "Moderate",
                "ONLINE REPORT": "https://example.test/candidate-002",
                "CLASSIFICATION DATE": "2024-02-02T00:00:00Z",
                "GCEP": "GCEP-C",
            },
            {
                "GENE SYMBOL": "GENE3",
                "GENE ID (HGNC)": "HGNC:3",
                "DISEASE LABEL": "disease three",
                "DISEASE ID (MONDO)": "MONDO:3",
                "MOI": "XL",
                "SOP": "SOP3",
                "CLASSIFICATION": "Limited",
                "ONLINE REPORT": "https://example.test/candidate-003",
                "CLASSIFICATION DATE": "2024-03-03T00:00:00Z",
                "GCEP": "GCEP-C",
            },
        ],
    )

    report = build_expansion_selection(
        ExpansionSelectionConfig(
            core_selection_path=ground_truth_root / "selection.json",
            source_csv_path=csv_path,
            output_path=ground_truth_root / "expansion_selection_20260615.json",
            target_size=2,
        )
    )

    assert report.summary.core_entry_count == 2
    assert report.summary.selected_count == 2
    assert report.summary.excluded_core_count == 1
    assert [entry.entry_id for entry in report.selected_entries] == ["clingen_030", "clingen_031"]
    assert all(entry.source_row_index in (1, 2) for entry in report.selected_entries)
    assert all("rarity" in entry.selection_reason for entry in report.selected_entries)


def test_expansion_selection_payload_and_writer(tmp_path: Path) -> None:
    ground_truth_root = tmp_path / "ground_truth"
    core_rows = [
        {
            "entry_id": "clingen_000",
            "clingen_report_url": "https://example.test/core-000",
            "gene_symbol": "GENE0",
            "disease_label": "core disease 0",
            "classification": "Definitive",
            "moi": "AD",
            "gcep": "GCEP-A",
        }
    ]
    _write_core_selection(ground_truth_root, core_rows)
    csv_path = _write_csv(
        tmp_path / "clingen.csv",
        [
            {
                "GENE SYMBOL": "GENE1",
                "GENE ID (HGNC)": "HGNC:1",
                "DISEASE LABEL": "disease one",
                "DISEASE ID (MONDO)": "MONDO:1",
                "MOI": "AR",
                "SOP": "SOP1",
                "CLASSIFICATION": "Moderate",
                "ONLINE REPORT": "https://example.test/candidate-001",
                "CLASSIFICATION DATE": "2024-02-01T00:00:00Z",
                "GCEP": "GCEP-B",
            }
        ],
    )

    report = build_expansion_selection(
        ExpansionSelectionConfig(
            core_selection_path=ground_truth_root / "selection.json",
            source_csv_path=csv_path,
            output_path=ground_truth_root / "expansion_selection_20260615.json",
            target_size=1,
        )
    )
    payload = expansion_selection_to_payload(report)
    report_path = write_expansion_selection(report, output_path=ground_truth_root / "expansion_selection_20260615.json")

    assert payload["summary"]["selected_count"] == 1
    assert payload["selected_entries"][0]["entry_id"] == "clingen_030"
    assert report_path.exists()
    assert report_path.name == "expansion_selection_20260615.json"
    assert "Selected=1/1" in format_expansion_selection(report)


def test_expansion_selection_uses_diversity_to_break_uniform_strength(tmp_path: Path) -> None:
    ground_truth_root = tmp_path / "ground_truth"
    _write_core_selection(
        ground_truth_root,
        [
            {
                "entry_id": "clingen_000",
                "clingen_report_url": "https://example.test/core-000",
                "gene_symbol": "CORE",
                "disease_label": "core disease",
                "classification": "Definitive",
                "moi": "AD",
                "gcep": "GCEP-A",
            }
        ],
    )
    csv_path = _write_csv(
        tmp_path / "clingen.csv",
        [
            {
                "GENE SYMBOL": "GENE1",
                "GENE ID (HGNC)": "HGNC:1",
                "DISEASE LABEL": "disease one",
                "DISEASE ID (MONDO)": "MONDO:1",
                "MOI": "AD",
                "SOP": "SOP1",
                "CLASSIFICATION": "Strong",
                "ONLINE REPORT": "https://example.test/candidate-001",
                "CLASSIFICATION DATE": "2024-02-01T00:00:00Z",
                "GCEP": "GCEP-B",
            },
            {
                "GENE SYMBOL": "GENE2",
                "GENE ID (HGNC)": "HGNC:2",
                "DISEASE LABEL": "disease two",
                "DISEASE ID (MONDO)": "MONDO:2",
                "MOI": "AR",
                "SOP": "SOP2",
                "CLASSIFICATION": "Moderate",
                "ONLINE REPORT": "https://example.test/candidate-002",
                "CLASSIFICATION DATE": "2024-03-02T00:00:00Z",
                "GCEP": "GCEP-C",
            },
            {
                "GENE SYMBOL": "GENE3",
                "GENE ID (HGNC)": "HGNC:3",
                "DISEASE LABEL": "disease three",
                "DISEASE ID (MONDO)": "MONDO:3",
                "MOI": "XL",
                "SOP": "SOP3",
                "CLASSIFICATION": "Strong",
                "ONLINE REPORT": "https://example.test/candidate-003",
                "CLASSIFICATION DATE": "2024-04-03T00:00:00Z",
                "GCEP": "GCEP-D",
            },
        ],
    )

    report = build_expansion_selection(
        ExpansionSelectionConfig(
            core_selection_path=ground_truth_root / "selection.json",
            source_csv_path=csv_path,
            output_path=ground_truth_root / "expansion_selection_20260615.json",
            target_size=2,
        )
    )

    assert [entry.classification for entry in report.selected_entries] == ["Moderate", "Strong"]
    assert report.summary.classification_counts == {"Moderate": 1, "Strong": 1}
