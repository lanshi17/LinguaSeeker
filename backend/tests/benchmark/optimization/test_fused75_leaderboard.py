"""Tests for fused-75 optimization leaderboard generation."""
from __future__ import annotations

import json
from pathlib import Path

from benchmark.optimization.fused75.build_leaderboard import build_leaderboard
from benchmark.optimization.fused75.run_contracts import (
    PipelineFlag,
    PipelineRunMetric,
    PipelineRunReport,
    PipelineVariantConfig,
    PipelineVariantDecision,
)


def _report(*, variant_id: str, split: str, f1: float, decision: str = "checkpoint_only") -> PipelineRunReport:
    return PipelineRunReport(
        config=PipelineVariantConfig(
            variant_id=variant_id,
            git_commit="a" * 40,
            dataset_split=split,
            pipeline_flags=(PipelineFlag(key="flag", value=variant_id),),
            model_config_names=("LLM_MODEL",),
        ),
        metric=PipelineRunMetric(
            runtime_seconds=10.0,
            llm_call_count=2,
            prompt_token_count=100,
            completion_token_count=20,
            total_token_count=120,
            precision=f1,
            recall=f1,
            f1=f1,
            source_visible_f1=f1,
        ),
        decision=PipelineVariantDecision(decision=decision, reason=f"{decision} variant"),
    )


def _write_report(path: Path, report: PipelineRunReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.to_stable_json() + "\n", encoding="utf-8")


def test_build_leaderboard_ranks_dev_variants_by_source_visible_f1(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    _write_report(reports_dir / "a_dev.json", _report(variant_id="variant-a", split="dev", f1=0.7))
    _write_report(reports_dir / "b_dev.json", _report(variant_id="variant-b", split="dev", f1=0.9))
    _write_report(reports_dir / "a_test.json", _report(variant_id="variant-a", split="test", f1=0.65))

    leaderboard = build_leaderboard(report_paths=tuple(sorted(reports_dir.glob("*.json"))))

    assert [row.variant_id for row in leaderboard.rows] == ["variant-b", "variant-a"]
    assert leaderboard.rows[0].dev_source_visible_f1 == 0.9
    assert leaderboard.rows[0].test_source_visible_f1 is None
    assert leaderboard.rows[1].test_source_visible_f1 == 0.65


def test_build_leaderboard_writes_stable_json_and_markdown(tmp_path: Path) -> None:
    report_path = tmp_path / "variant_dev.json"
    _write_report(report_path, _report(variant_id="variant-a", split="dev", f1=0.8, decision="rejected"))

    leaderboard = build_leaderboard(
        report_paths=(report_path,),
        json_output_path=tmp_path / "leaderboard.json",
        markdown_output_path=tmp_path / "leaderboard.md",
    )

    payload = json.loads((tmp_path / "leaderboard.json").read_text(encoding="utf-8"))
    markdown = (tmp_path / "leaderboard.md").read_text(encoding="utf-8")

    assert payload["rows"][0]["variant_id"] == "variant-a"
    assert payload["rows"][0]["decision"] == "rejected"
    assert "| variant-a | dev | 0.8000 |" in markdown
    assert leaderboard.rows[0].decision == "rejected"
