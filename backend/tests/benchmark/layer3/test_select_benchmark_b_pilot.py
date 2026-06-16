"""Tests for Benchmark B pilot selection."""
from __future__ import annotations

import json
from pathlib import Path

from benchmark.layer3.analysis.select_benchmark_b_pilot import (
    BenchmarkBPilotSelectionConfig,
    build_benchmark_b_pilot_selection,
    benchmark_b_pilot_selection_to_payload,
    format_benchmark_b_pilot_selection,
    write_benchmark_b_pilot_selection,
)


def _write_selection(root: Path, entry_ids: list[str]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "selection.json").write_text(
        json.dumps([{"entry_id": entry_id} for entry_id in entry_ids]),
        encoding="utf-8",
    )


def _write_source_pdf(source_root: Path, language: str, entry_id: str) -> Path:
    pdf_path = source_root / language / "case_report" / f"{entry_id}.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(b"%PDF-1.4\n%benchmark-b-pilot\n")
    return pdf_path


def test_benchmark_b_pilot_selector_excludes_english_only_entries_and_is_deterministic(
    tmp_path: Path,
) -> None:
    ground_truth_root = tmp_path / "ground_truth"
    source_root = tmp_path / "source_corpus"
    entry_ids = [f"clingen_{index:03d}" for index in range(12)]
    _write_selection(ground_truth_root, entry_ids)

    for entry_id in entry_ids[:10]:
        _write_source_pdf(source_root, "en", entry_id)
        _write_source_pdf(source_root, "zh", entry_id)
    for entry_id in entry_ids[10:]:
        _write_source_pdf(source_root, "en", entry_id)

    report = build_benchmark_b_pilot_selection(
        BenchmarkBPilotSelectionConfig(
            selection_path=ground_truth_root / "selection.json",
            source_corpus_root=source_root,
            output_path=ground_truth_root / "benchmark_b_pilot_selection.json",
            target_size=10,
        )
    )

    assert report.summary.total_frozen_entries == 12
    assert report.summary.selected_count == 10
    assert report.summary.excluded_english_only_count == 2
    assert report.summary.excluded_english_only_entry_ids == ("clingen_010", "clingen_011")
    assert [case.entry_id for case in report.selected_cases] == [f"clingen_{index:03d}" for index in range(10)]
    assert all("zh" in case.source_languages for case in report.selected_cases)
    assert all(case.non_english_source_count == 1 for case in report.selected_cases)


def test_benchmark_b_pilot_selector_writes_frozen_manifest(tmp_path: Path) -> None:
    ground_truth_root = tmp_path / "ground_truth"
    source_root = tmp_path / "source_corpus"
    entry_ids = [f"clingen_{index:03d}" for index in range(10)]
    _write_selection(ground_truth_root, entry_ids)

    for entry_id in entry_ids:
        _write_source_pdf(source_root, "en", entry_id)
        _write_source_pdf(source_root, "ja", entry_id)

    report = build_benchmark_b_pilot_selection(
        BenchmarkBPilotSelectionConfig(
            selection_path=ground_truth_root / "selection.json",
            source_corpus_root=source_root,
            output_path=ground_truth_root / "benchmark_b_pilot_selection.json",
            target_size=10,
        )
    )
    payload = benchmark_b_pilot_selection_to_payload(report)
    report_path = write_benchmark_b_pilot_selection(report, output_path=ground_truth_root / "benchmark_b_pilot_selection.json")

    assert payload["summary"]["selected_count"] == 10
    assert payload["selected_cases"][0]["source_files"][0]["path"].endswith("clingen_000.pdf")
    assert payload["selected_cases"][0]["source_files"][1]["path"].endswith("clingen_000.pdf")
    assert report_path.exists()
    assert report_path.name == "benchmark_b_pilot_selection.json"
    assert "PilotSelected=10/10" in format_benchmark_b_pilot_selection(report)


def test_benchmark_b_pilot_selector_default_source_root_finds_multilingual_case_reports(
    tmp_path: Path,
) -> None:
    selection_root = tmp_path / "ground_truth"
    source_root = tmp_path / "pipeline" / "input"
    entry_ids = [f"clingen_{index:03d}" for index in range(3)]
    _write_selection(selection_root, entry_ids)

    for entry_id in entry_ids:
        _write_source_pdf(source_root, "en", entry_id)
        _write_source_pdf(source_root, "ja", entry_id)

    report = build_benchmark_b_pilot_selection(
        BenchmarkBPilotSelectionConfig(
            selection_path=selection_root / "selection.json",
            source_corpus_root=source_root,
            output_path=selection_root / "benchmark_b_pilot_selection.json",
            target_size=10,
        )
    )

    assert report.summary.eligible_count == 3
    assert report.summary.selected_count == 3
    assert [case.entry_id for case in report.selected_cases] == entry_ids
    assert all(case.non_english_source_count == 1 for case in report.selected_cases)


def test_benchmark_b_pilot_selector_falls_back_to_latest_source_inventory_root(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    selection_root = tmp_path / "ground_truth"
    reports_root = tmp_path / "reports"
    source_root = repo_root / "benchmark" / "pipeline" / "input"
    entry_ids = [f"clingen_{index:03d}" for index in range(2)]
    _write_selection(selection_root, entry_ids)

    for entry_id in entry_ids:
        _write_source_pdf(source_root, "en", entry_id)
        _write_source_pdf(source_root, "ja", entry_id)

    inventory_path = reports_root / "source_inventory_20260616_000000.json"
    inventory_path.parent.mkdir(parents=True, exist_ok=True)
    inventory_path.write_text(
        json.dumps({"config": {"repo_root": str(repo_root)}}),
        encoding="utf-8",
    )

    report = build_benchmark_b_pilot_selection(
        BenchmarkBPilotSelectionConfig(
            selection_path=selection_root / "selection.json",
            source_corpus_root=selection_root / "missing-root",
            output_path=selection_root / "benchmark_b_pilot_selection.json",
            target_size=10,
        )
    )

    assert report.summary.eligible_count == 2
    assert report.summary.selected_count == 2
    assert report.warnings
    assert "fallback" in report.warnings[0]
