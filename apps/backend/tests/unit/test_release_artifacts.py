from __future__ import annotations

from pathlib import Path

from src.services.release_reporting import (
    calculate_release_gate_summary,
    load_acceptance_manifest,
)


def test_checked_in_release_artifacts_are_self_consistent() -> None:
    manifest = load_acceptance_manifest("../../docs/data/v1.0-100-paper-manifest.json")
    summary = calculate_release_gate_summary(manifest)
    report = Path("../../docs/reference/v1.0-release-report.md").read_text(encoding="utf-8")

    assert f"Gate status: {summary.gate_status}" in report
    if summary.completed_paper_count >= manifest.expected_paper_count:
        assert "acceptance run has not been executed yet" not in report.lower()
        assert "Actual 100-paper acceptance run remains unfinished." not in report
