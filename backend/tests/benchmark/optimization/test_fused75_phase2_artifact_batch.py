"""Tests for fused-75 Phase 2 artifact batch generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from benchmark.optimization.fused75.phase2_artifact_batch import (
    DEFAULT_FUSED75_GROUND_TRUTH_DIR,
    DEFAULT_FUSED75_REPORTS_DIR,
    DEFAULT_PIPELINE_ROOT,
    Fused75Phase2ArtifactBatchConfig,
    build_fused75_phase2_run_payload,
    load_fused75_phase2_batch_entries,
    run_fused75_phase2_artifact_batch,
)


def _write_fused_entry(root: Path, *, entry_id: str = "fused_001") -> None:
    selection = [
        {
            "entry_id": entry_id,
            "clingen": {
                "gene_symbol": "ABCA4",
                "disease_label": "ABCA4-related retinopathy",
            },
            "clinvar_variants": [
                {"hgvs_p": "p.Gly1961Glu"},
            ],
        }
    ]
    (root / "selection.json").write_text(json.dumps(selection), encoding="utf-8")
    entry_dir = root / entry_id
    entry_dir.mkdir(parents=True)
    (entry_dir / "source.md").write_text("# ABCA4 paper\nABCA4 c.5882G>A", encoding="utf-8")


def test_load_fused75_phase2_entries_reads_nested_selection_target(tmp_path: Path) -> None:
    _write_fused_entry(tmp_path)

    entries = load_fused75_phase2_batch_entries(
        Fused75Phase2ArtifactBatchConfig(
            ground_truth_dir=tmp_path,
            entry_ids=("fused_001",),
        )
    )

    assert len(entries) == 1
    assert entries[0].entry_id == "fused_001"
    assert entries[0].gene_symbol == "ABCA4"
    assert entries[0].disease_name == "ABCA4-related retinopathy"
    assert entries[0].variant_hgvs_p == "p.Gly1961Glu"
    assert entries[0].source_text.startswith("# ABCA4")


def test_default_pipeline_root_points_at_repo_backend_pipeline_dir() -> None:
    assert DEFAULT_PIPELINE_ROOT.name == "pipeline"
    assert DEFAULT_PIPELINE_ROOT.parent.name == "data"
    assert DEFAULT_PIPELINE_ROOT.parent.parent.name == "backend"
    assert DEFAULT_PIPELINE_ROOT.is_absolute()


def test_default_fused75_paths_are_repo_absolute() -> None:
    assert DEFAULT_FUSED75_GROUND_TRUTH_DIR.is_absolute()
    assert DEFAULT_FUSED75_GROUND_TRUTH_DIR.parts[-4:] == ("benchmark", "data", "ground_truth", "clinvar_fused")
    assert DEFAULT_FUSED75_REPORTS_DIR.is_absolute()
    assert DEFAULT_FUSED75_REPORTS_DIR.parts[-4:] == ("benchmark", "optimization", "fused75", "reports")


def test_build_fused75_phase2_payload_preserves_entry_target(tmp_path: Path) -> None:
    _write_fused_entry(tmp_path)
    entry = load_fused75_phase2_batch_entries(
        Fused75Phase2ArtifactBatchConfig(ground_truth_dir=tmp_path, entry_ids=("fused_001",))
    )[0]

    payload = build_fused75_phase2_run_payload(entry)

    assert payload["source_type"] == "local"
    assert payload["mode"] == "full"
    assert payload["filename"] == "fused_001.md"
    assert payload["pre_parsed_markdown"] == entry.source_text
    assert payload["target"] == {
        "gene_symbol": "ABCA4",
        "disease_name": "ABCA4-related retinopathy",
        "variant_hgvs_p": "p.Gly1961Glu",
        "clingen_entry_id": "fused_001",
    }


@pytest.mark.asyncio
async def test_run_fused75_phase2_batch_dry_run_reports_planned_entries(tmp_path: Path) -> None:
    _write_fused_entry(tmp_path)

    report = await run_fused75_phase2_artifact_batch(
        Fused75Phase2ArtifactBatchConfig(
            ground_truth_dir=tmp_path,
            entry_ids=("fused_001",),
            dry_run=True,
        )
    )

    assert report.total_entries == 1
    assert report.planned_count == 1
    assert report.rows[0].entry_id == "fused_001"
    assert report.rows[0].status == "planned"


@pytest.mark.asyncio
async def test_run_fused75_phase2_batch_materializes_completed_artifact(tmp_path: Path) -> None:
    _write_fused_entry(tmp_path)
    pipeline_artifact = tmp_path / "pipeline" / "run-1" / "phase_2" / "extraction_result.json"
    pipeline_artifact.parent.mkdir(parents=True)
    pipeline_artifact.write_text(json.dumps({"document_id": "doc-1"}), encoding="utf-8")
    client = _FakeClient(
        submission={"processing_run_id": "run-1", "source_document_id": "doc-1", "status_url": "/status/run-1"},
        statuses=[
            {
                "processing_run_id": "run-1",
                "source_document_id": "doc-1",
                "pipeline_status": "running",
                "current_phase": "phase_2",
                "phases": {"phase_2": {"status": "completed"}},
            }
        ],
    )

    report = await run_fused75_phase2_artifact_batch(
        Fused75Phase2ArtifactBatchConfig(
            ground_truth_dir=tmp_path,
            pipeline_root=tmp_path / "pipeline",
            entry_ids=("fused_001",),
            poll_interval_s=0,
            max_poll_attempts=1,
        ),
        client=client,
    )

    materialized = tmp_path / "fused_001" / "preprocessed" / "phase_2" / "extraction_result.json"
    assert report.completed_count == 1
    assert report.rows[0].artifact_exists is True
    assert materialized.exists()
    assert json.loads(materialized.read_text(encoding="utf-8")) == {"document_id": "doc-1"}
    assert client.submitted_payloads[0]["target"]["clingen_entry_id"] == "fused_001"


class _FakeResponse:
    def __init__(self, payload: dict[str, Any], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)

    def json(self) -> dict[str, Any]:
        return self._payload

    def raise_for_status(self) -> None:
        return None


class _FakeClient:
    def __init__(self, *, submission: dict[str, Any], statuses: list[dict[str, Any]]) -> None:
        self._submission = submission
        self._statuses = list(statuses)
        self.submitted_payloads: list[dict[str, Any]] = []

    async def post(self, _url: str, *, json: dict[str, Any], timeout: float) -> _FakeResponse:
        self.submitted_payloads.append(json)
        return _FakeResponse(self._submission)

    async def get(self, _url: str, *, timeout: float) -> _FakeResponse:
        return _FakeResponse(self._statuses.pop(0))
