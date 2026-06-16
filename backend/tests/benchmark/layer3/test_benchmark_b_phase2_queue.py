"""Tests for Benchmark B multilingual Phase 2 queue manifests."""
from __future__ import annotations

import json
from pathlib import Path

from benchmark.layer3.analysis.benchmark_b_phase2_queue import (
    BenchmarkBPhase2QueueConfig,
    benchmark_b_phase2_queue_to_payload,
    build_benchmark_b_phase2_queue,
    format_benchmark_b_phase2_queue,
    write_benchmark_b_phase2_queue,
)


def _write_selection(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            [
                {
                    "entry_id": "clingen_000",
                    "gene_symbol": "AARS1",
                    "disease_label": "Charcot-Marie-Tooth disease axonal type 2N",
                },
                {
                    "entry_id": "clingen_001",
                    "gene_symbol": "AARS2",
                    "disease_label": "mitochondrial disease",
                },
            ]
        ),
        encoding="utf-8",
    )


def _write_pilot(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "selected_cases": [
                    {
                        "entry_id": "clingen_000",
                        "source_languages": ["en", "zh", "ja", "ko"],
                        "source_files": [],
                        "non_english_source_count": 3,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


def _source_record(
    *,
    repo_root: Path,
    language: str,
    entry_id: str,
    literature_type: str = "case_report",
    source_database: str = "local_pdf",
) -> dict[str, object]:
    local_path = Path("benchmark") / "pipeline" / "input" / language / literature_type / f"{entry_id}.pdf"
    source_path = repo_root / local_path
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_bytes(b"%PDF-1.4\n%phase2-queue\n")
    return {
        "source_id": f"{source_database}:{local_path.as_posix()}",
        "source_kind": "raw_pdf",
        "source_database": source_database,
        "source_url": None,
        "article_language": language,
        "local_path": local_path.as_posix(),
        "sha256": f"sha-{language}-{entry_id}",
        "access_status": "local_copy",
        "annotation_status": "unlabeled",
        "benchmark_layer": "multilingual_pressure_test",
        "literature_type": literature_type,
    }


def _write_inventory(path: Path, repo_root: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    records = [
        _source_record(repo_root=repo_root, language="zh", entry_id="clingen_000"),
        _source_record(repo_root=repo_root, language="ja", entry_id="clingen_000"),
        _source_record(repo_root=repo_root, language="ko", entry_id="clingen_000"),
        _source_record(repo_root=repo_root, language="de", entry_id="clingen_000"),
        _source_record(repo_root=repo_root, language="zh", entry_id="clingen_001"),
        _source_record(repo_root=repo_root, language="zh", entry_id="clingen_000", literature_type="functional"),
    ]
    path.write_text(
        json.dumps(
            {
                "config": {"repo_root": str(repo_root)},
                "summary": {},
                "records": records,
                "warnings": [],
            }
        ),
        encoding="utf-8",
    )


def test_benchmark_b_phase2_queue_uses_only_pilot_main_language_case_reports(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    selection_path = tmp_path / "ground_truth" / "selection.json"
    pilot_path = tmp_path / "ground_truth" / "benchmark_b_pilot_selection.json"
    inventory_path = tmp_path / "reports" / "source_inventory.json"
    _write_selection(selection_path)
    _write_pilot(pilot_path)
    _write_inventory(inventory_path, repo_root)

    report = build_benchmark_b_phase2_queue(
        BenchmarkBPhase2QueueConfig(
            selection_path=selection_path,
            pilot_selection_path=pilot_path,
            source_inventory_path=inventory_path,
        )
    )

    assert report.summary.selected_case_count == 1
    assert report.summary.ready_source_count == 3
    assert report.summary.by_language == {"ja": 1, "ko": 1, "zh": 1}
    assert report.summary.missing_language_by_entry == {}
    assert [(item.entry_id, item.article_language) for item in report.items] == [
        ("clingen_000", "ja"),
        ("clingen_000", "ko"),
        ("clingen_000", "zh"),
    ]
    first = report.items[0]
    assert first.target_gene == "AARS1"
    assert first.target_disease == "Charcot-Marie-Tooth disease axonal type 2N"
    assert first.source_database == "local_pdf"
    assert first.annotation_status == "unlabeled"
    assert first.source_pdf_path.exists()


def test_benchmark_b_phase2_queue_reports_missing_pilot_languages(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    selection_path = tmp_path / "ground_truth" / "selection.json"
    pilot_path = tmp_path / "ground_truth" / "benchmark_b_pilot_selection.json"
    inventory_path = tmp_path / "reports" / "source_inventory.json"
    _write_selection(selection_path)
    _write_pilot(pilot_path)
    inventory_path.parent.mkdir(parents=True, exist_ok=True)
    inventory_path.write_text(
        json.dumps(
            {
                "config": {"repo_root": str(repo_root)},
                "records": [_source_record(repo_root=repo_root, language="zh", entry_id="clingen_000")],
            }
        ),
        encoding="utf-8",
    )

    report = build_benchmark_b_phase2_queue(
        BenchmarkBPhase2QueueConfig(
            selection_path=selection_path,
            pilot_selection_path=pilot_path,
            source_inventory_path=inventory_path,
        )
    )
    payload = benchmark_b_phase2_queue_to_payload(report)

    assert report.summary.ready_source_count == 1
    assert report.summary.missing_language_by_entry == {"clingen_000": ("ja", "ko")}
    assert payload["summary"]["missing_language_by_entry"] == {"clingen_000": ["ja", "ko"]}
    assert "QueuedSources=1" in format_benchmark_b_phase2_queue(report)


def test_write_benchmark_b_phase2_queue_persists_manifest(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    selection_path = tmp_path / "ground_truth" / "selection.json"
    pilot_path = tmp_path / "ground_truth" / "benchmark_b_pilot_selection.json"
    inventory_path = tmp_path / "reports" / "source_inventory.json"
    output_path = tmp_path / "ground_truth" / "benchmark_b_phase2_queue.json"
    _write_selection(selection_path)
    _write_pilot(pilot_path)
    inventory_path.parent.mkdir(parents=True, exist_ok=True)
    inventory_path.write_text(
        json.dumps(
            {
                "config": {"repo_root": str(repo_root)},
                "records": [_source_record(repo_root=repo_root, language="ko", entry_id="clingen_000")],
            }
        ),
        encoding="utf-8",
    )
    report = build_benchmark_b_phase2_queue(
        BenchmarkBPhase2QueueConfig(
            selection_path=selection_path,
            pilot_selection_path=pilot_path,
            source_inventory_path=inventory_path,
            output_path=output_path,
        )
    )

    written_path = write_benchmark_b_phase2_queue(report)
    payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert written_path == output_path
    assert payload["summary"]["ready_source_count"] == 1
    assert payload["items"][0]["entry_id"] == "clingen_000"
    assert payload["items"][0]["article_language"] == "ko"


def test_benchmark_b_phase2_queue_uses_absolute_paths_from_inventory(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    selection_path = tmp_path / "ground_truth" / "selection.json"
    pilot_path = tmp_path / "ground_truth" / "benchmark_b_pilot_selection.json"
    inventory_path = tmp_path / "reports" / "source_inventory.json"
    _write_selection(selection_path)
    _write_pilot(pilot_path)
    inventory_path.parent.mkdir(parents=True, exist_ok=True)
    inventory_path.write_text(
        json.dumps(
            {
                "config": {"repo_root": str(repo_root)},
                "records": [
                    _source_record(repo_root=repo_root, language="zh", entry_id="clingen_000"),
                    _source_record(repo_root=repo_root, language="ja", entry_id="clingen_000"),
                    _source_record(repo_root=repo_root, language="ko", entry_id="clingen_000"),
                ],
            }
        ),
        encoding="utf-8",
    )

    report = build_benchmark_b_phase2_queue(
        BenchmarkBPhase2QueueConfig(
            selection_path=selection_path,
            pilot_selection_path=pilot_path,
            source_inventory_path=inventory_path,
        )
    )

    assert report.summary.ready_source_count == 3
    assert all(item.source_pdf_path.exists() for item in report.items)
