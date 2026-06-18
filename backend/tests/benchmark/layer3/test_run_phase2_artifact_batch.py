"""Tests for Phase 2 artifact batch generation."""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from benchmark.runners.phase2_batch import (
    Phase2ArtifactBatchConfig,
    build_phase2_run_payload,
    load_phase2_batch_entries,
    load_phase2_batch_entries_from_coverage,
    phase2_artifact_batch_report_to_payload,
    run_phase2_artifact_batch,
)


def _write_entry(ground_truth_dir: Path, entry_id: str, *, source_text: str | None = None) -> None:
    entry_dir = ground_truth_dir / entry_id
    entry_dir.mkdir(parents=True)
    if source_text is not None:
        (entry_dir / "source.md").write_text(source_text, encoding="utf-8")


def _write_selection(ground_truth_dir: Path) -> None:
    ground_truth_dir.mkdir(parents=True)
    (ground_truth_dir / "selection.json").write_text(
        json.dumps(
            [
                {
                    "entry_id": "clingen_003",
                    "gene_symbol": "ABCA4",
                    "disease_label": "ABCA4-related retinopathy",
                },
                {
                    "entry_id": "clingen_004",
                    "gene_symbol": "ABCB11",
                    "disease_label": "progressive familial intrahepatic cholestasis 2",
                },
            ]
        ),
        encoding="utf-8",
    )


def test_build_phase2_run_payload_includes_traceable_target(tmp_path: Path) -> None:
    ground_truth_dir = tmp_path / "ground_truth"
    _write_selection(ground_truth_dir)
    _write_entry(ground_truth_dir, "clingen_003", source_text="A" * 120)

    entry = load_phase2_batch_entries(
        Phase2ArtifactBatchConfig(
            ground_truth_dir=ground_truth_dir,
            entry_ids=("clingen_003",),
        )
    )[0]
    payload = build_phase2_run_payload(entry)

    assert payload["source_type"] == "local"
    assert payload["mode"] == "full"
    assert payload["filename"] == "clingen_003.md"
    assert payload["pre_parsed_markdown"] == "A" * 120
    assert payload["target"] == {
        "gene_symbol": "ABCA4",
        "disease_name": "ABCA4-related retinopathy",
        "variant_hgvs_p": "",
        "clingen_entry_id": "clingen_003",
    }


def test_load_phase2_batch_entries_from_coverage_uses_only_missing_pipeline_rows(tmp_path: Path) -> None:
    ground_truth_dir = tmp_path / "ground_truth"
    coverage_path = tmp_path / "coverage.json"
    _write_selection(ground_truth_dir)
    _write_entry(ground_truth_dir, "clingen_003", source_text="A" * 120)
    _write_entry(ground_truth_dir, "clingen_004", source_text="B" * 120)
    coverage_path.write_text(
        json.dumps(
            {
                "rows": [
                    {"entry_id": "clingen_003", "status": "needs_pipeline_run"},
                    {"entry_id": "clingen_004", "status": "preprocessed"},
                ]
            }
        ),
        encoding="utf-8",
    )

    entries = load_phase2_batch_entries_from_coverage(
        Phase2ArtifactBatchConfig(
            ground_truth_dir=ground_truth_dir,
            coverage_report_path=coverage_path,
        )
    )

    assert [entry.entry_id for entry in entries] == ["clingen_003"]


@pytest.mark.asyncio
async def test_run_phase2_artifact_batch_stops_after_phase2_completed(tmp_path: Path) -> None:
    ground_truth_dir = tmp_path / "ground_truth"
    pipeline_root = tmp_path / "pipeline"
    _write_selection(ground_truth_dir)
    _write_entry(ground_truth_dir, "clingen_003", source_text="A" * 120)
    artifact_path = pipeline_root / "run-003" / "phase_2" / "extraction_result.json"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            posted = json.loads(request.content.decode("utf-8"))
            assert posted["target"]["clingen_entry_id"] == "clingen_003"
            return httpx.Response(
                202,
                json={
                    "processing_run_id": "run-003",
                    "source_document_id": "source-003",
                    "status": "accepted",
                    "status_url": "/api/v1/pipeline/runs/run-003/status",
                },
            )
        artifact_path.parent.mkdir(parents=True)
        artifact_path.write_text('{"ok": true}', encoding="utf-8")
        return httpx.Response(
            200,
            json={
                "processing_run_id": "run-003",
                "source_document_id": "source-003",
                "pipeline_status": "running",
                "current_phase": "phase_3",
                "phases": {
                    "phase_1": {"status": "completed"},
                    "phase_2": {"status": "completed"},
                    "phase_3": {"status": "running"},
                },
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        report = await run_phase2_artifact_batch(
            Phase2ArtifactBatchConfig(
                ground_truth_dir=ground_truth_dir,
                pipeline_root=pipeline_root,
                entry_ids=("clingen_003",),
                poll_interval_s=0,
                max_poll_attempts=2,
            ),
            client=client,
        )

    assert len(report.rows) == 1
    row = report.rows[0]
    assert row.status == "phase2_completed"
    assert row.processing_run_id == "run-003"
    assert row.phase2_status == "completed"
    assert row.pipeline_status == "running"
    assert row.artifact_path == artifact_path
    assert row.artifact_exists is True
    assert report.completed_count == 1
    assert phase2_artifact_batch_report_to_payload(report)["completed_count"] == 1


@pytest.mark.asyncio
async def test_run_phase2_artifact_batch_dry_run_writes_planned_rows(tmp_path: Path) -> None:
    ground_truth_dir = tmp_path / "ground_truth"
    _write_selection(ground_truth_dir)
    _write_entry(ground_truth_dir, "clingen_003", source_text="A" * 120)

    report = await run_phase2_artifact_batch(
        Phase2ArtifactBatchConfig(
            ground_truth_dir=ground_truth_dir,
            entry_ids=("clingen_003",),
            dry_run=True,
        )
    )

    assert report.rows[0].status == "planned"
    assert report.rows[0].processing_run_id is None
