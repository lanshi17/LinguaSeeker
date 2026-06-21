"""Build a fused-75 optimization leaderboard from variant run reports."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from pydantic import BaseModel, ConfigDict, ValidationError

from benchmark.optimization.fused75.run_contracts import PipelineRunReport

_DEFAULT_REPORTS_DIR = Path("benchmark/optimization/fused75/reports")


class LeaderboardRow(BaseModel):
    """One variant row in the optimization leaderboard."""

    model_config = ConfigDict(frozen=True)

    variant_id: str
    decision: str
    best_split: str
    dev_source_visible_f1: float | None
    test_source_visible_f1: float | None
    runtime_seconds: float
    llm_call_count: int
    total_token_count: int
    entry_coverage: str


class LeaderboardReport(BaseModel):
    """Ranked fused-75 optimization leaderboard."""

    model_config = ConfigDict(frozen=True)

    rows: tuple[LeaderboardRow, ...]


def build_leaderboard(
    *,
    report_paths: tuple[Path, ...],
    json_output_path: Path | None = None,
    markdown_output_path: Path | None = None,
) -> LeaderboardReport:
    """Build and optionally write a leaderboard from run report paths."""
    reports = tuple(_load_report(path) for path in report_paths)
    rows = tuple(sorted(_rows_by_variant(reports), key=_sort_key))
    leaderboard = LeaderboardReport(rows=rows)
    if json_output_path:
        _write_json(leaderboard, json_output_path)
    if markdown_output_path:
        _write_markdown(leaderboard, markdown_output_path)
    return leaderboard


def discover_run_report_paths(reports_dir: Path) -> tuple[Path, ...]:
    """Discover fused-75 run reports while ignoring other report JSON files."""
    paths: list[Path] = []
    for path in sorted(reports_dir.glob("*.json")):
        try:
            _load_report(path)
        except (json.JSONDecodeError, ValidationError):
            continue
        paths.append(path)
    return tuple(paths)


def _load_report(path: Path) -> PipelineRunReport:
    return PipelineRunReport.model_validate_json(path.read_text(encoding="utf-8"))


def _rows_by_variant(reports: tuple[PipelineRunReport, ...]) -> tuple[LeaderboardRow, ...]:
    variant_ids = sorted({report.config.variant_id for report in reports})
    rows: list[LeaderboardRow] = []
    for variant_id in variant_ids:
        variant_reports = tuple(report for report in reports if report.config.variant_id == variant_id)
        dev_report = _best_report(variant_reports, split="dev")
        test_report = _best_report(variant_reports, split="test")
        primary = dev_report or test_report or variant_reports[0]
        rows.append(
            LeaderboardRow(
                variant_id=variant_id,
                decision=primary.decision.decision,
                best_split=primary.config.dataset_split,
                dev_source_visible_f1=_eligible_f1(dev_report),
                test_source_visible_f1=_eligible_f1(test_report),
                runtime_seconds=primary.metric.runtime_seconds,
                llm_call_count=primary.metric.llm_call_count,
                total_token_count=primary.metric.total_token_count,
                entry_coverage=_coverage(primary),
            )
        )
    return tuple(rows)


def _best_report(reports: tuple[PipelineRunReport, ...], *, split: str) -> PipelineRunReport | None:
    matching = tuple(report for report in reports if report.config.dataset_split == split)
    if not matching:
        return None
    return max(matching, key=lambda report: _eligible_f1(report) if _eligible_f1(report) is not None else -1.0)


def _eligible_f1(report: PipelineRunReport | None) -> float | None:
    if report is None:
        return None
    if report.artifact_status.missing_artifact_entry_ids:
        return None
    return report.metric.source_visible_f1


def _coverage(report: PipelineRunReport) -> str:
    status = report.artifact_status
    return f"{status.evaluated_entry_count}/{status.expected_entry_count}"


def _sort_key(row: LeaderboardRow) -> tuple[float, str]:
    return (-(row.dev_source_visible_f1 if row.dev_source_visible_f1 is not None else -1.0), row.variant_id)


def _write_json(leaderboard: LeaderboardReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(leaderboard.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_markdown(leaderboard: LeaderboardReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Fused-75 Optimization Leaderboard",
        "",
        "| Variant | Best Split | Entry Coverage | Dev Source-Visible F1 | Test Source-Visible F1 | Decision | Runtime Seconds | LLM Calls | Tokens |",
        "|---|---|---:|---:|---:|---|---:|---:|---:|",
    ]
    for row in leaderboard.rows:
        lines.append(
            "| "
            f"{row.variant_id} | "
            f"{row.best_split} | "
            f"{row.entry_coverage} | "
            f"{_fmt_score(row.dev_source_visible_f1)} | "
            f"{_fmt_score(row.test_source_visible_f1)} | "
            f"{row.decision} | "
            f"{row.runtime_seconds:.4f} | "
            f"{row.llm_call_count} | "
            f"{row.total_token_count} |"
        )
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _fmt_score(value: float | None) -> str:
    return "NA" if value is None else f"{value:.4f}"


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports-dir", type=Path, default=_DEFAULT_REPORTS_DIR)
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    """CLI entry point."""
    args = _parse_args(argv)
    build_leaderboard(
        report_paths=discover_run_report_paths(args.reports_dir),
        json_output_path=args.json_output,
        markdown_output_path=args.markdown_output,
    )


if __name__ == "__main__":
    main()
