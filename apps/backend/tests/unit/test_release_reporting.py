from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.services.release_report_cli import main as release_report_main
from src.services.release_reporting import (
    AcceptanceManifest,
    calculate_release_gate_summary,
    render_release_report,
)


def test_acceptance_manifest_accepts_entry_kind_source_and_request_payload() -> None:
    manifest = AcceptanceManifest.model_validate(
        {
            "release_no": "v1.0",
            "locked": True,
            "expected_paper_count": 1,
            "papers": [
                {
                    "paper_id": "api-001",
                    "entry_kind": "api",
                    "source": "pmc",
                    "request_payload": {"query": "BARD1"},
                    "request_id": "req-1",
                    "status": "queued",
                }
            ],
        }
    )

    assert manifest.papers[0].entry_kind == "api"
    assert manifest.papers[0].source == "pmc"
    assert manifest.papers[0].request_payload == {"query": "BARD1"}
    assert manifest.papers[0].request_id == "req-1"


def test_release_gate_summary_ignores_execution_metadata_for_counts() -> None:
    manifest = AcceptanceManifest.model_validate(
        {
            "release_no": "v1.0",
            "locked": True,
            "expected_paper_count": 1,
            "papers": [
                {
                    "paper_id": "api-001",
                    "entry_kind": "api",
                    "source": "pmc",
                    "request_payload": {"query": "BARD1"},
                    "request_id": "req-1",
                    "status": "queued",
                }
            ],
        }
    )

    summary = calculate_release_gate_summary(manifest)

    assert summary.manifest_entry_count == 1
    assert summary.completed_paper_count == 0
    assert summary.pending_paper_count == 1


def test_calculate_release_gate_counts_file_duplicate_as_success() -> None:
    manifest = AcceptanceManifest.model_validate(
        {
            "release_no": "v1.0",
            "locked": True,
            "expected_paper_count": 4,
            "papers": [
                {"paper_id": "paper-1", "status": "success", "duration_seconds": 120},
                {
                    "paper_id": "paper-2",
                    "status": "success",
                    "error_code": "FILE_DUPLICATE",
                    "duration_seconds": 0,
                },
                {"paper_id": "paper-3", "status": "failed", "duration_seconds": 130},
                {"paper_id": "paper-4", "status": "success", "duration_seconds": 140},
            ],
        }
    )

    summary = calculate_release_gate_summary(manifest)

    assert summary.gate_status == "FAILED"
    assert summary.success_count == 3
    assert summary.duplicate_count == 1
    assert summary.success_rate_numerator == 3
    assert summary.success_rate_denominator == 4
    assert "SUCCESS_RATE_BELOW_THRESHOLD" in summary.blocking_reasons


def test_calculate_release_gate_marks_incomplete_when_run_not_finished() -> None:
    manifest = AcceptanceManifest.model_validate(
        {
            "release_no": "v1.0",
            "locked": True,
            "expected_paper_count": 100,
            "notes": ["Actual 100-paper acceptance run remains unfinished."],
            "papers": [
                {"paper_id": "paper-1", "status": "success", "duration_seconds": 120},
                {"paper_id": "paper-2", "status": "running"},
            ],
        }
    )

    summary = calculate_release_gate_summary(manifest)

    assert summary.gate_status == "INCOMPLETE"
    assert summary.completed_paper_count == 1
    assert summary.pending_paper_count == 99
    assert "RUN_INCOMPLETE" in summary.blocking_reasons


def test_render_release_report_mentions_gate_status_and_notes() -> None:
    manifest = AcceptanceManifest.model_validate(
        {
            "release_no": "v1.0",
            "locked": False,
            "expected_paper_count": 100,
            "notes": ["Actual 100-paper acceptance run remains unfinished."],
            "papers": [],
        }
    )

    summary = calculate_release_gate_summary(manifest)
    rendered = render_release_report(manifest, summary)

    assert "# Release Report: v1.0" in rendered
    assert "Gate status: INCOMPLETE" in rendered
    assert "Actual 100-paper acceptance run remains unfinished." in rendered


def test_render_release_report_drops_unfinished_note_for_terminal_manifest() -> None:
    manifest = AcceptanceManifest.model_validate(
        {
            "release_no": "v1.0",
            "locked": True,
            "expected_paper_count": 1,
            "notes": ["Actual 100-paper acceptance run remains unfinished."],
            "papers": [
                {"paper_id": "paper-a", "status": "success", "duration_seconds": 120.0}
            ],
        }
    )

    summary = calculate_release_gate_summary(manifest)
    rendered = render_release_report(manifest, summary)

    assert "Actual 100-paper acceptance run remains unfinished." not in rendered
    assert "Acceptance run reached terminal state:" in rendered



def test_render_release_report_uses_render_timestamp_not_manifest_generated_at() -> None:
    manifest = AcceptanceManifest.model_validate(
        {
            "release_no": "v1.0",
            "locked": True,
            "generated_at": "2026-04-07T00:00:00+00:00",
            "expected_paper_count": 1,
            "papers": [
                {"paper_id": "paper-a", "status": "success", "duration_seconds": 120.0}
            ],
        }
    )

    summary = calculate_release_gate_summary(manifest)
    rendered = render_release_report(
        manifest,
        summary,
        rendered_at=datetime(2026, 4, 10, 8, 0, tzinfo=timezone.utc),
    )

    assert "Generated at: 2026-04-10T08:00:00+00:00" in rendered
    assert "Generated at: 2026-04-07T00:00:00+00:00" not in rendered



def test_release_report_cli_writes_markdown_report(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    output_path = tmp_path / "release-report.md"
    manifest_path.write_text(
        json.dumps(
            {
                "release_no": "v1.0",
                "locked": False,
                "expected_paper_count": 100,
                "notes": ["Actual 100-paper acceptance run remains unfinished."],
                "papers": [],
            }
        ),
        encoding="utf-8",
    )

    exit_code = release_report_main(
        ["--manifest", str(manifest_path), "--output", str(output_path)]
    )

    assert exit_code == 0
    rendered = output_path.read_text(encoding="utf-8")
    assert "# Release Report: v1.0" in rendered
    assert "Gate status: INCOMPLETE" in rendered
