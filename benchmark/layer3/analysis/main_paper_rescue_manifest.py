"""Frozen baseline manifest for BIBM Main Paper rescue work."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import time
from typing import Any, Mapping, TypedDict, cast

from benchmark.layer3.evaluate import GROUND_TRUTH_DIR, REPORTS_DIR


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

    source_report_path: str
    baseline_strategy: str
    candidate_strategy: str
    sample_size: int
    baseline_f1: float
    candidate_f1: float
    delta_f1: float
    bootstrap_ci_low: float
    bootstrap_ci_high: float
    sign_test_p: float
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
    source_inventory_report: str | None
    traceability_report: str | None
    benchmark_a_readiness_report: str | None
    benchmark_b_pilot_selection_report: str | None
    alignment_report: str | None
    evidence_augmentation_report: str | None
    benchmark_b_runtime_report: str | None
    baseline_reports: list[str]


class ReproducibilityPayload(TypedDict):
    """Serializable reproducibility ledger."""

    git_commit: str
    entry_ids: list[str]
    generated_reports: list[str]
    commands: Mapping[str, str]


class NoLeakagePayload(TypedDict):
    """Serializable no-leakage declaration."""

    uses_expected_fields_at_runtime: bool
    uses_clingen_classification_at_runtime: bool
    allowed_runtime_context: list[str]


class MainPaperRescueManifestPayload(TypedDict):
    """Serializable Main Paper rescue manifest."""

    generated_at: str
    git_commit: str
    source_reports: SourceReportsPayload
    reproducibility: ReproducibilityPayload
    no_leakage: NoLeakagePayload
    coverage: CoveragePayload
    strategies: list[StrategyMetricPayload]
    g2_statistics: G2SummaryPayload
    baselines: list[BaselineReportPayload]
    source_inventory_summary: dict[str, object]


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

    source_report_path: Path
    baseline_strategy: str
    candidate_strategy: str
    sample_size: int
    baseline_f1: float
    candidate_f1: float
    delta_f1: float
    bootstrap_ci_low: float
    bootstrap_ci_high: float
    sign_test_p: float
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
class ReproducibilityLedger:
    """Commands and identifiers required to reproduce a frozen paper run."""

    git_commit: str
    entry_ids: tuple[str, ...]
    generated_reports: tuple[Path, ...]
    commands: Mapping[str, str]


@dataclass(frozen=True)
class NoLeakageDeclaration:
    """Runtime-input declaration for reviewer-facing no-leakage checks."""

    uses_expected_fields_at_runtime: bool
    uses_clingen_classification_at_runtime: bool
    allowed_runtime_context: tuple[str, ...]


@dataclass(frozen=True)
class MainPaperRescueManifest:
    """Complete frozen baseline manifest for rescue experiments."""

    generated_at: str
    git_commit: str
    coverage_report_path: Path
    ablation_report_path: Path
    g2_report_path: Path
    source_inventory_report_path: Path | None
    traceability_report_path: Path | None
    benchmark_a_readiness_report_path: Path | None
    benchmark_b_pilot_selection_report_path: Path | None
    alignment_report_path: Path | None
    evidence_augmentation_report_path: Path | None
    benchmark_b_runtime_report_path: Path | None
    reproducibility: ReproducibilityLedger
    no_leakage: NoLeakageDeclaration
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
    entry_ids: tuple[str, ...] | None = None,
    ground_truth_root: Path | None = None,
    source_inventory_report_path: Path | None = None,
    traceability_report_path: Path | None = None,
    benchmark_a_readiness_report_path: Path | None = None,
    benchmark_b_pilot_selection_report_path: Path | None = None,
    alignment_report_path: Path | None = None,
    evidence_augmentation_report_path: Path | None = None,
    benchmark_b_runtime_report_path: Path | None = None,
    commands: Mapping[str, str] | None = None,
    no_leakage: NoLeakageDeclaration | None = None,
) -> MainPaperRescueManifest:
    """Build a frozen manifest from existing benchmark reports."""
    coverage_payload = _load_json_object(coverage_report_path)
    ablation_payload = _load_json_object(ablation_report_path)
    g2_payload = _load_json_object(g2_report_path)
    baseline_payloads = tuple(_load_json_object(path) for path in baseline_report_paths)
    if source_inventory_report_path is not None and not source_inventory_report_path.exists():
        raise FileNotFoundError(source_inventory_report_path)
    if traceability_report_path is not None and not traceability_report_path.exists():
        raise FileNotFoundError(traceability_report_path)
    if benchmark_a_readiness_report_path is not None and not benchmark_a_readiness_report_path.exists():
        raise FileNotFoundError(benchmark_a_readiness_report_path)
    if benchmark_b_pilot_selection_report_path is not None and not benchmark_b_pilot_selection_report_path.exists():
        raise FileNotFoundError(benchmark_b_pilot_selection_report_path)
    if alignment_report_path is not None and not alignment_report_path.exists():
        raise FileNotFoundError(alignment_report_path)
    if evidence_augmentation_report_path is not None and not evidence_augmentation_report_path.exists():
        raise FileNotFoundError(evidence_augmentation_report_path)
    if benchmark_b_runtime_report_path is not None and not benchmark_b_runtime_report_path.exists():
        raise FileNotFoundError(benchmark_b_runtime_report_path)
    frozen_entry_ids = _resolve_entry_ids(
        explicit_entry_ids=entry_ids,
        ablation_payload=ablation_payload,
        baseline_payloads=baseline_payloads,
        ground_truth_root=ground_truth_root or GROUND_TRUTH_DIR,
    )
    g2_summary = _g2_summary(g2_payload)
    _validate_report_alignment(
        coverage_payload=coverage_payload,
        ablation_payload=ablation_payload,
        g2_summary=g2_summary,
        baseline_payloads=baseline_payloads,
        ablation_report_path=ablation_report_path,
        entry_ids=frozen_entry_ids,
    )
    commit = git_commit or _current_git_commit()
    return MainPaperRescueManifest(
        generated_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        git_commit=commit,
        coverage_report_path=coverage_report_path,
        ablation_report_path=ablation_report_path,
        g2_report_path=g2_report_path,
        traceability_report_path=traceability_report_path,
        source_inventory_report_path=source_inventory_report_path,
        alignment_report_path=alignment_report_path,
        evidence_augmentation_report_path=evidence_augmentation_report_path,
        benchmark_b_runtime_report_path=benchmark_b_runtime_report_path,
        benchmark_a_readiness_report_path=benchmark_a_readiness_report_path,
        benchmark_b_pilot_selection_report_path=benchmark_b_pilot_selection_report_path,
        reproducibility=ReproducibilityLedger(
            git_commit=commit,
            entry_ids=frozen_entry_ids,
            generated_reports=_generated_report_paths(
                coverage_report_path=coverage_report_path,
                ablation_report_path=ablation_report_path,
                g2_report_path=g2_report_path,
                source_inventory_report_path=source_inventory_report_path,
                traceability_report_path=traceability_report_path,
                benchmark_a_readiness_report_path=benchmark_a_readiness_report_path,
                benchmark_b_pilot_selection_report_path=benchmark_b_pilot_selection_report_path,
                alignment_report_path=alignment_report_path,
                evidence_augmentation_report_path=evidence_augmentation_report_path,
                benchmark_b_runtime_report_path=benchmark_b_runtime_report_path,
                baseline_report_paths=baseline_report_paths,
            ),
            commands=commands
            or _default_commands(
                coverage_report_path=coverage_report_path,
                ablation_report_path=ablation_report_path,
                g2_report_path=g2_report_path,
                source_inventory_report_path=source_inventory_report_path,
                traceability_report_path=traceability_report_path,
                benchmark_a_readiness_report_path=benchmark_a_readiness_report_path,
                benchmark_b_pilot_selection_report_path=benchmark_b_pilot_selection_report_path,
                alignment_report_path=alignment_report_path,
                evidence_augmentation_report_path=evidence_augmentation_report_path,
                benchmark_b_runtime_report_path=benchmark_b_runtime_report_path,
                baseline_report_paths=baseline_report_paths,
            ),
        ),
        no_leakage=no_leakage or _default_no_leakage_declaration(),
        coverage=_coverage_summary(coverage_payload),
        strategies=tuple(_strategy_metrics(ablation_payload)),
        g2_statistics=g2_summary,
        baselines=tuple(
            _baseline_summary(path, payload)
            for path, payload in zip(baseline_report_paths, baseline_payloads, strict=True)
        ),
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
            "source_inventory_report": (
                str(manifest.source_inventory_report_path) if manifest.source_inventory_report_path else None
            ),
            "traceability_report": str(manifest.traceability_report_path) if manifest.traceability_report_path else None,
            "benchmark_a_readiness_report": (
                str(manifest.benchmark_a_readiness_report_path)
                if manifest.benchmark_a_readiness_report_path
                else None
            ),
            "benchmark_b_pilot_selection_report": (
                str(manifest.benchmark_b_pilot_selection_report_path)
                if manifest.benchmark_b_pilot_selection_report_path
                else None
            ),
            "alignment_report": str(manifest.alignment_report_path) if manifest.alignment_report_path else None,
            "evidence_augmentation_report": (
                str(manifest.evidence_augmentation_report_path)
                if manifest.evidence_augmentation_report_path
                else None
            ),
            "benchmark_b_runtime_report": (
                str(manifest.benchmark_b_runtime_report_path)
                if manifest.benchmark_b_runtime_report_path
                else None
            ),
            "baseline_reports": [str(summary.report_path) for summary in manifest.baselines],
        },
        "reproducibility": {
            "git_commit": manifest.reproducibility.git_commit,
            "entry_ids": list(manifest.reproducibility.entry_ids),
            "generated_reports": [str(report_path) for report_path in manifest.reproducibility.generated_reports],
            "commands": manifest.reproducibility.commands,
        },
        "no_leakage": {
            "uses_expected_fields_at_runtime": manifest.no_leakage.uses_expected_fields_at_runtime,
            "uses_clingen_classification_at_runtime": manifest.no_leakage.uses_clingen_classification_at_runtime,
            "allowed_runtime_context": list(manifest.no_leakage.allowed_runtime_context),
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
            "source_report_path": str(manifest.g2_statistics.source_report_path),
            "baseline_strategy": manifest.g2_statistics.baseline_strategy,
            "candidate_strategy": manifest.g2_statistics.candidate_strategy,
            "sample_size": manifest.g2_statistics.sample_size,
            "baseline_f1": manifest.g2_statistics.baseline_f1,
            "candidate_f1": manifest.g2_statistics.candidate_f1,
            "delta_f1": manifest.g2_statistics.delta_f1,
            "bootstrap_ci_low": manifest.g2_statistics.bootstrap_ci_low,
            "bootstrap_ci_high": manifest.g2_statistics.bootstrap_ci_high,
            "sign_test_p": manifest.g2_statistics.sign_test_p,
            "significant": manifest.g2_statistics.significant,
            "main_paper_ready": manifest.g2_statistics.main_paper_ready,
        },
        "source_inventory_summary": _load_source_inventory_summary(manifest.source_inventory_report_path),
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
    parser.add_argument("--source-inventory-report", type=Path, default=None)
    parser.add_argument("--traceability-report", type=Path, default=None)
    parser.add_argument("--benchmark-a-readiness-report", type=Path, default=None)
    parser.add_argument("--benchmark-b-pilot-selection-report", type=Path, default=None)
    parser.add_argument("--alignment-report", type=Path, default=None)
    parser.add_argument("--evidence-augmentation-report", type=Path, default=None)
    parser.add_argument("--benchmark-b-runtime-report", type=Path, default=None)
    parser.add_argument("--entry-id", action="append", default=[])
    parser.add_argument("--ground-truth-root", type=Path, default=GROUND_TRUTH_DIR)
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    manifest = build_manifest(
        coverage_report_path=args.coverage_report,
        ablation_report_path=args.ablation_report,
        g2_report_path=args.g2_report,
        baseline_report_paths=tuple(args.baseline_report),
        entry_ids=tuple(args.entry_id) or None,
        ground_truth_root=args.ground_truth_root,
        source_inventory_report_path=args.source_inventory_report,
        traceability_report_path=args.traceability_report,
        benchmark_a_readiness_report_path=args.benchmark_a_readiness_report,
        benchmark_b_pilot_selection_report_path=args.benchmark_b_pilot_selection_report,
        alignment_report_path=args.alignment_report,
        evidence_augmentation_report_path=args.evidence_augmentation_report,
        benchmark_b_runtime_report_path=args.benchmark_b_runtime_report,
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
        source_report_path=Path(str(payload.get("source_report_path", ""))),
        baseline_strategy=str(payload.get("baseline_strategy", "")),
        candidate_strategy=str(payload.get("candidate_strategy", "")),
        sample_size=int(payload.get("sample_size", 0)),
        baseline_f1=float(payload.get("baseline_f1", 0.0)),
        candidate_f1=float(payload.get("candidate_f1", 0.0)),
        delta_f1=float(payload.get("delta_f1", 0.0)),
        bootstrap_ci_low=float(payload.get("bootstrap_ci_low", 0.0)),
        bootstrap_ci_high=float(payload.get("bootstrap_ci_high", 0.0)),
        sign_test_p=float(payload.get("sign_test_p", 1.0)),
        significant=bool(payload.get("significant", False)),
        main_paper_ready=bool(payload.get("main_paper_ready", False)),
    )


def _baseline_summary(path: Path, payload: Mapping[str, Any]) -> BaselineReportSummary:
    aggregates = payload.get("aggregates", {})
    if not isinstance(aggregates, dict):
        aggregates = {}
    overall = aggregates.get("overall", {})
    if not isinstance(overall, dict):
        overall = {}
    return BaselineReportSummary(
        label=str(payload.get("label") or payload.get("baseline_id") or _label_from_path(path)),
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


def _resolve_entry_ids(
    *,
    explicit_entry_ids: tuple[str, ...] | None,
    ablation_payload: Mapping[str, Any],
    baseline_payloads: tuple[Mapping[str, Any], ...],
    ground_truth_root: Path,
) -> tuple[str, ...]:
    """Resolve the frozen benchmark entry set in order of authority."""
    if explicit_entry_ids:
        return explicit_entry_ids

    ablation_entry_ids = _entry_ids_from_ablation(ablation_payload)
    if ablation_entry_ids:
        return ablation_entry_ids

    for baseline_payload in baseline_payloads:
        baseline_entry_ids = _entry_ids_from_payload(baseline_payload)
        if baseline_entry_ids:
            return baseline_entry_ids

    selection_entry_ids = _entry_ids_from_selection(ground_truth_root / "selection.json")
    if selection_entry_ids:
        return selection_entry_ids

    directory_entry_ids = tuple(
        path.name
        for path in sorted(ground_truth_root.iterdir())
        if path.is_dir()
    ) if ground_truth_root.exists() else ()
    if not directory_entry_ids:
        raise ValueError("Could not resolve frozen entry_ids from reports or ground_truth_root")
    return directory_entry_ids


def _entry_ids_from_ablation(payload: Mapping[str, Any]) -> tuple[str, ...]:
    strategies = payload.get("strategies", [])
    if not isinstance(strategies, list):
        return ()
    for strategy in strategies:
        if not isinstance(strategy, Mapping):
            continue
        entry_ids = _entry_ids_from_payload(strategy)
        if entry_ids:
            return entry_ids
    return ()


def _entry_ids_from_payload(payload: Mapping[str, Any]) -> tuple[str, ...]:
    raw_per_entry = payload.get("per_entry")
    if not isinstance(raw_per_entry, list):
        return ()
    return tuple(
        str(entry["entry_id"])
        for entry in raw_per_entry
        if isinstance(entry, Mapping) and entry.get("entry_id")
    )


def _entry_ids_from_selection(selection_path: Path) -> tuple[str, ...]:
    if not selection_path.exists():
        return ()
    payload = json.loads(selection_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return ()
    return tuple(
        str(entry["entry_id"])
        for entry in payload
        if isinstance(entry, Mapping) and entry.get("entry_id")
    )


def _validate_report_alignment(
    *,
    coverage_payload: Mapping[str, Any],
    ablation_payload: Mapping[str, Any],
    g2_summary: G2Summary,
    baseline_payloads: tuple[Mapping[str, Any], ...],
    ablation_report_path: Path,
    entry_ids: tuple[str, ...],
) -> None:
    expected_n = len(entry_ids)
    if not _same_path(g2_summary.source_report_path, ablation_report_path):
        raise ValueError(
            "G2 source_report_path must match the manifest ablation_report_path: "
            f"{g2_summary.source_report_path} != {ablation_report_path}"
        )

    _validate_total_entries("coverage_report", coverage_payload, expected_n)
    _validate_ablation_entries(ablation_payload, entry_ids)
    if g2_summary.sample_size != expected_n:
        raise ValueError(f"g2_statistics sample_size={g2_summary.sample_size} does not match N={expected_n}")

    for baseline_payload in baseline_payloads:
        label = str(baseline_payload.get("label") or baseline_payload.get("baseline_id") or "baseline")
        _validate_total_entries(label, baseline_payload, expected_n)
        _validate_entry_ids(label, _entry_ids_from_payload(baseline_payload), entry_ids)


def _validate_ablation_entries(payload: Mapping[str, Any], entry_ids: tuple[str, ...]) -> None:
    strategies = payload.get("strategies", [])
    if not isinstance(strategies, list):
        raise ValueError("ablation_report strategies must be a list")
    for strategy in strategies:
        if not isinstance(strategy, Mapping):
            continue
        strategy_name = str(strategy.get("strategy") or "unknown_strategy")
        _validate_total_entries(strategy_name, strategy, len(entry_ids))
        _validate_entry_ids(strategy_name, _entry_ids_from_payload(strategy), entry_ids)


def _validate_total_entries(label: str, payload: Mapping[str, Any], expected_n: int) -> None:
    if "total_entries" not in payload:
        return
    total_entries = int(payload.get("total_entries", 0))
    if total_entries != expected_n:
        raise ValueError(f"{label} total_entries={total_entries} does not match frozen N={expected_n}")


def _validate_entry_ids(label: str, observed_entry_ids: tuple[str, ...], expected_entry_ids: tuple[str, ...]) -> None:
    if not observed_entry_ids:
        return
    if len(observed_entry_ids) != len(expected_entry_ids) or set(observed_entry_ids) != set(expected_entry_ids):
        raise ValueError(f"{label} entry_ids do not match the frozen manifest entry_ids")


def _same_path(left: Path, right: Path) -> bool:
    return left.expanduser().resolve() == right.expanduser().resolve()


def _generated_report_paths(
    *,
    coverage_report_path: Path,
    ablation_report_path: Path,
    g2_report_path: Path,
    source_inventory_report_path: Path | None,
    traceability_report_path: Path | None,
    benchmark_a_readiness_report_path: Path | None,
    benchmark_b_pilot_selection_report_path: Path | None,
    alignment_report_path: Path | None,
    evidence_augmentation_report_path: Path | None,
    benchmark_b_runtime_report_path: Path | None,
    baseline_report_paths: tuple[Path, ...],
) -> tuple[Path, ...]:
    report_paths: list[Path] = [coverage_report_path, ablation_report_path, g2_report_path]
    if source_inventory_report_path is not None:
        report_paths.append(source_inventory_report_path)
    if traceability_report_path is not None:
        report_paths.append(traceability_report_path)
    if benchmark_a_readiness_report_path is not None:
        report_paths.append(benchmark_a_readiness_report_path)
    if benchmark_b_pilot_selection_report_path is not None:
        report_paths.append(benchmark_b_pilot_selection_report_path)
    if alignment_report_path is not None:
        report_paths.append(alignment_report_path)
    if evidence_augmentation_report_path is not None:
        report_paths.append(evidence_augmentation_report_path)
    if benchmark_b_runtime_report_path is not None:
        report_paths.append(benchmark_b_runtime_report_path)
    report_paths.extend(baseline_report_paths)
    return tuple(report_paths)


def _default_commands(
    *,
    coverage_report_path: Path,
    ablation_report_path: Path,
    g2_report_path: Path,
    source_inventory_report_path: Path | None,
    traceability_report_path: Path | None,
    benchmark_a_readiness_report_path: Path | None,
    benchmark_b_pilot_selection_report_path: Path | None,
    alignment_report_path: Path | None,
    evidence_augmentation_report_path: Path | None,
    benchmark_b_runtime_report_path: Path | None,
    baseline_report_paths: tuple[Path, ...],
) -> Mapping[str, str]:
    manifest_parts = [
        "PYTHONPATH=.:backend uv run --project backend --no-sync",
        "python -m benchmark.layer3.analysis.main_paper_rescue_manifest",
        f"--coverage-report {coverage_report_path}",
        f"--ablation-report {ablation_report_path}",
        f"--g2-report {g2_report_path}",
    ]
    if source_inventory_report_path is not None:
        manifest_parts.append(f"--source-inventory-report {source_inventory_report_path}")
    if traceability_report_path is not None:
        manifest_parts.append(f"--traceability-report {traceability_report_path}")
    if benchmark_a_readiness_report_path is not None:
        manifest_parts.append(f"--benchmark-a-readiness-report {benchmark_a_readiness_report_path}")
    if benchmark_b_pilot_selection_report_path is not None:
        manifest_parts.append(f"--benchmark-b-pilot-selection-report {benchmark_b_pilot_selection_report_path}")
    if alignment_report_path is not None:
        manifest_parts.append(f"--alignment-report {alignment_report_path}")
    if evidence_augmentation_report_path is not None:
        manifest_parts.append(f"--evidence-augmentation-report {evidence_augmentation_report_path}")
    if benchmark_b_runtime_report_path is not None:
        manifest_parts.append(f"--benchmark-b-runtime-report {benchmark_b_runtime_report_path}")
    for baseline_report_path in baseline_report_paths:
        manifest_parts.append(f"--baseline-report {baseline_report_path}")
    manifest_parts.append("--write")
    return {
        "coverage": "PYTHONPATH=.:backend uv run --project backend --no-sync "
        "python -m benchmark.layer3.analysis.phase2_artifact_coverage --write",
        "ablation": "PYTHONPATH=.:backend uv run --project backend --no-sync "
        "python -m benchmark.layer3.analysis.reconcile_ablation --write",
        "baselines": "PYTHONPATH=.:backend uv run --project backend --no-sync "
        "python -m benchmark.layer3.analysis.diagnose_baselines --write",
        "benchmark_a_readiness": "PYTHONPATH=.:backend uv run --project backend --no-sync "
        "python -m benchmark.layer3.analysis.benchmark_readiness --write",
        "source_inventory": "PYTHONPATH=.:backend uv run --project backend --no-sync "
        "python -m benchmark.layer3.analysis.source_inventory --write",
        "benchmark_b_pilot_selection": "PYTHONPATH=.:backend uv run --project backend --no-sync "
        "python -m benchmark.layer3.analysis.select_benchmark_b_pilot --write",
        "g2_statistics": "PYTHONPATH=.:backend uv run --project backend --no-sync "
        "python -m benchmark.layer3.analysis.g2_statistics "
        f"--report {ablation_report_path} "
        "--baseline-strategy grounded_hard_rule "
        "--candidate-strategy context_verifier_reconcile --write",
        "manifest": " ".join(manifest_parts),
    }


def _load_source_inventory_summary(source_inventory_report_path: Path | None) -> dict[str, object]:
    """Load the summary section from a source inventory report, or return empty defaults."""
    if source_inventory_report_path is None or not source_inventory_report_path.exists():
        return {}
    payload = _load_json_object(source_inventory_report_path)
    summary = payload.get("summary")
    if not isinstance(summary, Mapping):
        return {}
    return {
        "clinvar_fused_entry_count": int(summary.get("clinvar_fused_entry_count", 0)),
        "main_multilingual_pdf_count": int(summary.get("main_multilingual_pdf_count", 0)),
        "structured_anchor_count": int(summary.get("structured_anchor_count", 0)),
        "raw_pdf_count": int(summary.get("raw_pdf_count", 0)),
    }


def _default_no_leakage_declaration() -> NoLeakageDeclaration:
    return NoLeakageDeclaration(
        uses_expected_fields_at_runtime=False,
        uses_clingen_classification_at_runtime=False,
        allowed_runtime_context=(
            "source article text and metadata",
            "runtime extraction artifacts",
            "ontology and context-pack metadata",
            "report-level evaluation outputs for analysis only",
        ),
    )


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
