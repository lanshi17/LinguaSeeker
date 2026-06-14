"""Frozen baseline manifest for BIBM Main Paper rescue work."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import time
from typing import Any, Mapping, TypedDict, cast

from benchmark.layer3.evaluate import REPORTS_DIR


class CoveragePayload(TypedDict):
    """Serializable Phase 2 artifact coverage summary."""

    total_entries: int
    covered_count: int
    needs_pipeline_count: int


class StrategyMetricPayload(TypedDict):
    """Serializable strategy metric summary."""

    strategy: str
    total_entries: int
    precision: float
    recall: float
    f1: float


class G2SummaryPayload(TypedDict):
    """Serializable G2 gate summary."""

    baseline_strategy: str
    candidate_strategy: str
    sample_size: int
    baseline_f1: float
    candidate_f1: float
    delta_f1: float
    bootstrap_ci_low: float
    bootstrap_ci_high: float
    significant: bool
    main_paper_ready: bool


class BaselineReportPayload(TypedDict):
    """Serializable external baseline report summary."""

    label: str
    report_path: str
    total_entries: int
    precision: float
    recall: float
    f1: float


class SourceReportsPayload(TypedDict):
    """Manifest source report paths."""

    coverage_report: str
    ablation_report: str
    g2_report: str
    baseline_reports: list[str]


class MainPaperRescueManifestPayload(TypedDict):
    """Serializable Main Paper rescue manifest."""

    generated_at: str
    git_commit: str
    source_reports: SourceReportsPayload
    coverage: CoveragePayload
    strategies: list[StrategyMetricPayload]
    g2_statistics: G2SummaryPayload
    baselines: list[BaselineReportPayload]


@dataclass(frozen=True)
class CoverageSummary:
    """Phase 2 artifact coverage summary."""

    total_entries: int
    covered_count: int
    needs_pipeline_count: int


@dataclass(frozen=True)
class StrategyMetric:
    """Overall metrics for one ablation strategy."""

    strategy: str
    total_entries: int
    precision: float
    recall: float
    f1: float


@dataclass(frozen=True)
class G2Summary:
    """Frozen G2 gate result."""

    baseline_strategy: str
    candidate_strategy: str
    sample_size: int
    baseline_f1: float
    candidate_f1: float
    delta_f1: float
    bootstrap_ci_low: float
    bootstrap_ci_high: float
    significant: bool
    main_paper_ready: bool


@dataclass(frozen=True)
class BaselineReportSummary:
    """Summary for a full baseline report."""

    label: str
    report_path: Path
    total_entries: int
    precision: float
    recall: float
    f1: float


@dataclass(frozen=True)
class MainPaperRescueManifest:
    """Complete frozen baseline manifest for rescue experiments."""

    generated_at: str
    git_commit: str
    coverage_report_path: Path
    ablation_report_path: Path
    g2_report_path: Path
    coverage: CoverageSummary
    strategies: tuple[StrategyMetric, ...]
    g2_statistics: G2Summary
    baselines: tuple[BaselineReportSummary, ...]


def build_manifest(
    *,
    coverage_report_path: Path,
    ablation_report_path: Path,
    g2_report_path: Path,
    baseline_report_paths: tuple[Path, ...],
    git_commit: str | None = None,
) -> MainPaperRescueManifest:
    """Build a frozen manifest from existing benchmark reports."""
    coverage_payload = _load_json_object(coverage_report_path)
    ablation_payload = _load_json_object(ablation_report_path)
    g2_payload = _load_json_object(g2_report_path)
    return MainPaperRescueManifest(
        generated_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        git_commit=git_commit or _current_git_commit(),
        coverage_report_path=coverage_report_path,
        ablation_report_path=ablation_report_path,
        g2_report_path=g2_report_path,
        coverage=_coverage_summary(coverage_payload),
        strategies=tuple(_strategy_metrics(ablation_payload)),
        g2_statistics=_g2_summary(g2_payload),
        baselines=tuple(_baseline_summary(path) for path in baseline_report_paths),
    )


def manifest_to_payload(manifest: MainPaperRescueManifest) -> MainPaperRescueManifestPayload:
    """Convert a manifest into a JSON-serializable payload."""
    return {
        "generated_at": manifest.generated_at,
        "git_commit": manifest.git_commit,
        "source_reports": {
            "coverage_report": str(manifest.coverage_report_path),
            "ablation_report": str(manifest.ablation_report_path),
            "g2_report": str(manifest.g2_report_path),
            "baseline_reports": [str(summary.report_path) for summary in manifest.baselines],
        },
        "coverage": {
            "total_entries": manifest.coverage.total_entries,
            "covered_count": manifest.coverage.covered_count,
            "needs_pipeline_count": manifest.coverage.needs_pipeline_count,
        },
        "strategies": [
            {
                "strategy": metric.strategy,
                "total_entries": metric.total_entries,
                "precision": metric.precision,
                "recall": metric.recall,
                "f1": metric.f1,
            }
            for metric in manifest.strategies
        ],
        "g2_statistics": {
            "baseline_strategy": manifest.g2_statistics.baseline_strategy,
            "candidate_strategy": manifest.g2_statistics.candidate_strategy,
            "sample_size": manifest.g2_statistics.sample_size,
            "baseline_f1": manifest.g2_statistics.baseline_f1,
            "candidate_f1": manifest.g2_statistics.candidate_f1,
            "delta_f1": manifest.g2_statistics.delta_f1,
            "bootstrap_ci_low": manifest.g2_statistics.bootstrap_ci_low,
            "bootstrap_ci_high": manifest.g2_statistics.bootstrap_ci_high,
            "significant": manifest.g2_statistics.significant,
            "main_paper_ready": manifest.g2_statistics.main_paper_ready,
        },
        "baselines": [
            {
                "label": baseline.label,
                "report_path": str(baseline.report_path),
                "total_entries": baseline.total_entries,
                "precision": baseline.precision,
                "recall": baseline.recall,
                "f1": baseline.f1,
            }
            for baseline in manifest.baselines
        ],
    }


def write_manifest(
    manifest: MainPaperRescueManifest,
    reports_dir: Path = REPORTS_DIR,
) -> Path:
    """Persist a Main Paper rescue manifest."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"main_paper_rescue_manifest_{time.strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(
        json.dumps(manifest_to_payload(manifest), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report_path


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint for manifest generation."""
    parser = argparse.ArgumentParser(description="Write a frozen BIBM Main Paper rescue manifest.")
    parser.add_argument("--coverage-report", type=Path, required=True)
    parser.add_argument("--ablation-report", type=Path, required=True)
    parser.add_argument("--g2-report", type=Path, required=True)
    parser.add_argument("--baseline-report", type=Path, action="append", default=[])
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    manifest = build_manifest(
        coverage_report_path=args.coverage_report,
        ablation_report_path=args.ablation_report,
        g2_report_path=args.g2_report,
        baseline_report_paths=tuple(args.baseline_report),
    )
    if args.write:
        print(f"REPORT: {write_manifest(manifest, reports_dir=args.reports_dir)}")
    else:
        print(json.dumps(manifest_to_payload(manifest), ensure_ascii=False, indent=2))


def _load_json_object(path: Path) -> Mapping[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return cast(Mapping[str, Any], payload)


def _coverage_summary(payload: Mapping[str, Any]) -> CoverageSummary:
    return CoverageSummary(
        total_entries=int(payload.get("total_entries", 0)),
        covered_count=int(payload.get("covered_count", 0)),
        needs_pipeline_count=int(payload.get("needs_pipeline_count", 0)),
    )


def _strategy_metrics(payload: Mapping[str, Any]) -> list[StrategyMetric]:
    metrics: list[StrategyMetric] = []
    for raw_strategy in payload.get("strategies", []):
        if not isinstance(raw_strategy, dict):
            continue
        aggregates = raw_strategy.get("aggregates", {})
        if not isinstance(aggregates, dict):
            aggregates = {}
        overall = aggregates.get("overall", {})
        if not isinstance(overall, dict):
            overall = {}
        metrics.append(
            StrategyMetric(
                strategy=str(raw_strategy.get("strategy", "")),
                total_entries=int(raw_strategy.get("total_entries", 0)),
                precision=float(overall.get("precision", 0.0)),
                recall=float(overall.get("recall", 0.0)),
                f1=float(overall.get("f1", 0.0)),
            )
        )
    return metrics


def _g2_summary(payload: Mapping[str, Any]) -> G2Summary:
    return G2Summary(
        baseline_strategy=str(payload.get("baseline_strategy", "")),
        candidate_strategy=str(payload.get("candidate_strategy", "")),
        sample_size=int(payload.get("sample_size", 0)),
        baseline_f1=float(payload.get("baseline_f1", 0.0)),
        candidate_f1=float(payload.get("candidate_f1", 0.0)),
        delta_f1=float(payload.get("delta_f1", 0.0)),
        bootstrap_ci_low=float(payload.get("bootstrap_ci_low", 0.0)),
        bootstrap_ci_high=float(payload.get("bootstrap_ci_high", 0.0)),
        significant=bool(payload.get("significant", False)),
        main_paper_ready=bool(payload.get("main_paper_ready", False)),
    )


def _baseline_summary(path: Path) -> BaselineReportSummary:
    payload = _load_json_object(path)
    aggregates = payload.get("aggregates", {})
    if not isinstance(aggregates, dict):
        aggregates = {}
    overall = aggregates.get("overall", {})
    if not isinstance(overall, dict):
        overall = {}
    return BaselineReportSummary(
        label=str(payload.get("label") or _label_from_path(path)),
        report_path=path,
        total_entries=int(payload.get("total_entries", 0)),
        precision=float(overall.get("precision", 0.0)),
        recall=float(overall.get("recall", 0.0)),
        f1=float(overall.get("f1", 0.0)),
    )


def _label_from_path(path: Path) -> str:
    stem = path.stem
    if stem.startswith("baseline_"):
        return stem.split("_", maxsplit=2)[1].upper()
    return stem


def _current_git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return result.stdout.strip()


if __name__ == "__main__":
    main()
