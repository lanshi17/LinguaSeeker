"""Run a fused-75 pipeline variant against adjudicated entries."""
from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Sequence

from benchmark.optimization.fused75.adjudication_contracts import Fused75EntryAdjudication
from benchmark.optimization.fused75.evaluate_adjudicated import ExtractedItem, evaluate_adjudicated_entry
from benchmark.optimization.fused75.run_contracts import (
    PipelineRunArtifactStatus,
    PipelineRunMetric,
    PipelineRunReport,
    PipelineVariantConfig,
    PipelineVariantDecision,
)

PipelineRunSplit = Literal["dev", "test", "auto_pool"]

_DEFAULT_CONFIG_PATH = Path("benchmark/optimization/fused75/variant_config.json")
_DEFAULT_ADJUDICATION_ROOT = Path("benchmark/optimization/fused75/adjudication")
_DEFAULT_EXTRACTION_ROOT = Path("benchmark/optimization/fused75/extractions")
_DEFAULT_FUSED_GROUND_TRUTH_ROOT = Path("benchmark/data/ground_truth/clinvar_fused")
_DEFAULT_OUTPUT_PATH = Path("benchmark/optimization/fused75/reports/variant_report.json")


@dataclass(frozen=True)
class PipelineExtractionItem:
    """Extracted item normalized for adjudicated evaluation."""

    field_id: str
    value: str


def run_variant(
    *,
    split: PipelineRunSplit,
    config_path: Path,
    adjudication_root: Path = _DEFAULT_ADJUDICATION_ROOT,
    extraction_root: Path = _DEFAULT_EXTRACTION_ROOT,
    fused_ground_truth_root: Path = _DEFAULT_FUSED_GROUND_TRUTH_ROOT,
    output_path: Path = _DEFAULT_OUTPUT_PATH,
    checkpoint: bool = False,
    allow_missing_artifacts: bool = False,
) -> PipelineRunReport:
    """Run a variant over existing extraction artifacts and write a report."""
    if split == "test" and not checkpoint:
        raise ValueError("Running the frozen test split requires checkpoint=True")

    config = PipelineVariantConfig.model_validate_json(config_path.read_text(encoding="utf-8"))
    if config.dataset_split != split:
        raise ValueError(f"config dataset_split={config.dataset_split} does not match requested split={split}")
    start = time.perf_counter()
    adjudications = _load_adjudications(split=split, adjudication_root=adjudication_root)
    incomplete = tuple(adjudication.entry_id for adjudication in adjudications if not adjudication.is_complete)
    if incomplete:
        raise ValueError(f"incomplete adjudication entries: {', '.join(incomplete)}")
    totals = _Totals()
    missing_artifact_entry_ids: list[str] = []
    evaluated_entry_count = 0
    for adjudication in adjudications:
        extraction_path = _resolve_extraction_path(
            entry_id=adjudication.entry_id,
            extraction_root=extraction_root,
            fused_ground_truth_root=fused_ground_truth_root,
        )
        if extraction_path is None:
            missing_artifact_entry_ids.append(adjudication.entry_id)
            continue
        result = evaluate_adjudicated_entry(
            adjudication,
            extracted_items=_load_items(extraction_path),
        )
        totals.add(tp=result.metric.tp, fp=result.metric.fp, fn=result.metric.fn)
        evaluated_entry_count += 1

    if missing_artifact_entry_ids and not allow_missing_artifacts:
        raise FileNotFoundError(
            "missing extraction artifacts for entries: "
            f"{', '.join(missing_artifact_entry_ids)}. "
            "Pass allow_missing_artifacts=True only for coverage diagnostics."
        )

    precision, recall, f1 = totals.scores()
    metric = PipelineRunMetric(
        runtime_seconds=round(time.perf_counter() - start, 6),
        llm_call_count=0,
        prompt_token_count=0,
        completion_token_count=0,
        total_token_count=0,
        precision=precision,
        recall=recall,
        f1=f1,
        source_visible_f1=f1,
    )
    decision_reason = f"Recorded {split} variant run"
    if missing_artifact_entry_ids:
        decision_reason = (
            f"Partial {split} run; missing {len(missing_artifact_entry_ids)} "
            "extraction artifacts, not eligible for full-split ranking"
        )
    report = PipelineRunReport(
        config=config,
        metric=metric,
        decision=PipelineVariantDecision(decision="checkpoint_only", reason=decision_reason),
        artifact_status=PipelineRunArtifactStatus(
            expected_entry_count=len(adjudications),
            evaluated_entry_count=evaluated_entry_count,
            missing_artifact_entry_ids=tuple(missing_artifact_entry_ids),
        ),
    )
    _write_report(report, output_path)
    return report


@dataclass
class _Totals:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    def add(self, *, tp: int, fp: int, fn: int) -> None:
        self.tp += tp
        self.fp += fp
        self.fn += fn

    def scores(self) -> tuple[float, float, float]:
        precision = self.tp / (self.tp + self.fp) if self.tp + self.fp else 0.0
        recall = self.tp / (self.tp + self.fn) if self.tp + self.fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        return round(precision, 4), round(recall, 4), round(f1, 4)


def _load_adjudications(*, split: PipelineRunSplit, adjudication_root: Path) -> tuple[Fused75EntryAdjudication, ...]:
    if split == "auto_pool":
        return ()
    split_dir = "dev" if split == "dev" else "test"
    paths = sorted((adjudication_root / split_dir).glob("*.json"))
    return tuple(Fused75EntryAdjudication.model_validate_json(path.read_text(encoding="utf-8")) for path in paths)


def _load_items(path: Path) -> tuple[ExtractedItem, ...]:
    payload = _load_json(path)
    items = _extract_items(payload)
    return tuple(PipelineExtractionItem(field_id=str(item["field_id"]), value=str(item["value"])) for item in items)


def _resolve_extraction_path(
    *,
    entry_id: str,
    extraction_root: Path,
    fused_ground_truth_root: Path,
) -> Path | None:
    explicit_path = extraction_root / f"{entry_id}.json"
    if explicit_path.exists():
        return explicit_path
    preprocessed_path = fused_ground_truth_root / entry_id / "preprocessed" / "phase_2" / "extraction_result.json"
    if preprocessed_path.exists():
        return preprocessed_path
    return None


def _extract_items(payload: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    if isinstance(payload.get("items"), list):
        return tuple(_found_items(payload["items"]))

    reconciled = payload.get("reconciled_result")
    if isinstance(reconciled, dict) and isinstance(reconciled.get("evidence_items"), list):
        return tuple(_found_items(reconciled["evidence_items"]))

    merged: list[dict[str, Any]] = []
    for track_key in ("original_result", "translated_result"):
        track = payload.get(track_key)
        if isinstance(track, dict) and isinstance(track.get("evidence_items"), list):
            merged.extend(_found_items(track["evidence_items"]))
    return tuple(merged)


def _found_items(items: Sequence[Any]) -> tuple[dict[str, Any], ...]:
    found: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("status", "found") != "found":
            continue
        if item.get("field_id") is None or item.get("value") is None:
            continue
        found.append(item)
    return tuple(found)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


def _write_report(report: PipelineRunReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report.to_stable_json() + "\n", encoding="utf-8")


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("dev", "test", "auto_pool"), required=True)
    parser.add_argument("--config", type=Path, default=_DEFAULT_CONFIG_PATH)
    parser.add_argument("--adjudication-root", type=Path, default=_DEFAULT_ADJUDICATION_ROOT)
    parser.add_argument("--extraction-root", type=Path, default=_DEFAULT_EXTRACTION_ROOT)
    parser.add_argument("--fused-ground-truth-root", type=Path, default=_DEFAULT_FUSED_GROUND_TRUTH_ROOT)
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT_PATH)
    parser.add_argument("--checkpoint", action="store_true")
    parser.add_argument("--allow-missing-artifacts", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    """CLI entry point."""
    args = _parse_args(argv)
    run_variant(
        split=args.split,
        config_path=args.config,
        adjudication_root=args.adjudication_root,
        extraction_root=args.extraction_root,
        fused_ground_truth_root=args.fused_ground_truth_root,
        output_path=args.output,
        checkpoint=args.checkpoint,
        allow_missing_artifacts=args.allow_missing_artifacts,
    )


if __name__ == "__main__":
    main()
