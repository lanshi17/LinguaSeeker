"""Tests for runtime Benchmark B phase 2 augmentation metrics."""
from __future__ import annotations

import json
from pathlib import Path

from benchmark.analysis.benchmark_b.phase2_runtime_metrics import (
    BenchmarkBPhase2RuntimeConfig,
    benchmark_b_phase2_runtime_report_to_payload,
    build_benchmark_b_phase2_runtime_report,
)


def _write_sample_report(
    path: Path,
    *,
    status: str,
    artifact_path: str | None,
    queue_id: str = "clingen_000:ja",
    article_language: str = "ja",
) -> Path:
    path.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "queue_id": queue_id,
                        "entry_id": "clingen_000",
                        "article_language": article_language,
                        "target_gene": "AARS1",
                        "target_disease": "Charcot-Marie-Tooth disease axonal type 2N",
                        "processing_run_id": "run-1",
                        "source_document_id": "doc-1",
                        "pipeline_status": "running",
                        "phase2_status": "completed" if status == "phase2_completed" else "pending",
                        "status": status,
                        "source_pdf_path": "/tmp/sample.pdf",
                        "artifact_path": artifact_path,
                        "artifact_exists": artifact_path is not None,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_artifact(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "reconciled_result": {
                    "evidence_items": [
                        {
                            "field_id": "A.gene_symbol",
                            "value": "AARS1",
                            "status": "found",
                            "is_english": False,
                            "evidence_source_language": "ja",
                            "source": {"span_id": "span-1", "text_snippet": "AARS1"},
                        },
                        {
                            "field_id": "A.gene_symbol",
                            "value": "AARS1",
                            "status": "found",
                            "is_english": True,
                            "evidence_source_language": "en",
                            "source": {"span_id": "span-2", "text_snippet": "AARS1"},
                        },
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    return path


def test_runtime_report_skips_non_completed_rows_and_deduplicates_artifacts(tmp_path: Path) -> None:
    artifact = _write_artifact(tmp_path / "pipeline" / "run-1" / "phase_2" / "extraction_result.json")
    sample_1 = _write_sample_report(tmp_path / "sample-1.json", status="phase2_completed", artifact_path=str(artifact))
    sample_2 = _write_sample_report(tmp_path / "sample-2.json", status="timeout", artifact_path=str(artifact))

    report = build_benchmark_b_phase2_runtime_report(
        BenchmarkBPhase2RuntimeConfig(sample_report_paths=(sample_1, sample_2))
    )

    assert len(report.per_case) == 1
    assert report.per_case[0].phase2_status == "completed"
    assert report.overall.non_english_evidence_yield == 0.5


def test_runtime_report_recovers_late_completed_artifact_from_timeout_row(tmp_path: Path) -> None:
    artifact = _write_artifact(tmp_path / "pipeline" / "run-1" / "phase_2" / "extraction_result.json")
    sample = _write_sample_report(tmp_path / "sample.json", status="timeout", artifact_path=str(artifact))

    report = build_benchmark_b_phase2_runtime_report(BenchmarkBPhase2RuntimeConfig(sample_report_paths=(sample,)))

    assert len(report.per_case) == 1
    assert report.per_case[0].phase2_status == "completed"
    assert report.per_case[0].artifact_exists is True
    assert report.overall.non_english_evidence_yield == 0.5


def test_runtime_report_does_not_recover_timeout_without_artifact_path(tmp_path: Path) -> None:
    sample = _write_sample_report(tmp_path / "sample.json", status="timeout", artifact_path=None)

    report = build_benchmark_b_phase2_runtime_report(BenchmarkBPhase2RuntimeConfig(sample_report_paths=(sample,)))

    assert report.per_case == ()


def test_runtime_report_counts_unique_attempted_samples_and_timeouts(tmp_path: Path) -> None:
    artifact = _write_artifact(tmp_path / "pipeline" / "run-1" / "phase_2" / "extraction_result.json")
    completed_sample = _write_sample_report(
        tmp_path / "sample-1.json",
        status="phase2_completed",
        artifact_path=str(artifact),
    )
    timeout_sample = _write_sample_report(
        tmp_path / "sample-2.json",
        status="timeout",
        artifact_path=None,
        queue_id="clingen_000:zh",
        article_language="zh",
    )

    report = build_benchmark_b_phase2_runtime_report(
        BenchmarkBPhase2RuntimeConfig(sample_report_paths=(completed_sample, timeout_sample))
    )
    payload = benchmark_b_phase2_runtime_report_to_payload(report)

    assert payload["runtime_summary"]["attempted_samples"] == 2
    assert payload["runtime_summary"]["phase2_completed"] == 1
    assert payload["runtime_summary"]["timeout_count"] == 1
    assert payload["runtime_summary"]["failed_count"] == 1
    assert payload["runtime_summary"]["completed_queue_ids"] == ["clingen_000:ja"]
    assert payload["runtime_summary"]["incomplete_queue_ids"] == ["clingen_000:zh"]


def test_runtime_report_prefers_completed_row_over_late_timeout_for_same_queue_id(tmp_path: Path) -> None:
    late_artifact = _write_artifact(tmp_path / "pipeline" / "run-1" / "phase_2" / "extraction_result.json")
    completed_artifact = _write_artifact(tmp_path / "pipeline" / "run-2" / "phase_2" / "extraction_result.json")
    late_sample = _write_sample_report(tmp_path / "sample-1.json", status="timeout", artifact_path=str(late_artifact))
    completed_sample = _write_sample_report(
        tmp_path / "sample-2.json",
        status="phase2_completed",
        artifact_path=str(completed_artifact),
    )

    report = build_benchmark_b_phase2_runtime_report(
        BenchmarkBPhase2RuntimeConfig(sample_report_paths=(late_sample, completed_sample))
    )

    assert len(report.per_case) == 1
    assert report.per_case[0].artifact_path == completed_artifact
    assert report.overall.non_english_evidence_yield == 0.5


def test_runtime_report_uses_flat_reconciled_result_payload(tmp_path: Path) -> None:
    artifact = tmp_path / "pipeline" / "run-1" / "phase_2" / "extraction_result.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        json.dumps(
            {
                "evidence_items": [
                    {
                        "field_id": "A.gene_symbol",
                        "value": "AARS1",
                        "status": "found",
                        "is_english": False,
                        "evidence_source_language": "ja",
                        "source": {"span_id": "span-1", "text_snippet": "AARS1"},
                    },
                    {
                        "field_id": "A.gene_symbol",
                        "value": "AARS1",
                        "status": "found",
                        "is_english": True,
                        "evidence_source_language": "en",
                        "source": {"span_id": "span-2", "text_snippet": "AARS1"},
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    sample = _write_sample_report(
        tmp_path / "sample.json",
        status="phase2_completed",
        artifact_path=str(artifact),
    )

    report = build_benchmark_b_phase2_runtime_report(BenchmarkBPhase2RuntimeConfig(sample_report_paths=(sample,)))

    assert report.overall.non_english_evidence_yield == 0.5
