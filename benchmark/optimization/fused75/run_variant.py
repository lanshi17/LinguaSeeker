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
    PipelineRunMetric,
    PipelineRunReport,
    PipelineVariantConfig,
    PipelineVariantDecision,
)

PipelineRunSplit = Literal["dev", "test", "auto_pool"]

_DEFAULT_CONFIG_PATH = Path("benchmark/optimization/fused75/variant_config.json")
_DEFAULT_ADJUDICATION_ROOT = Path("benchmark/optimization/fused75/adjudication")
_DEFAULT_EXTRACTION_ROOT = Path("benchmark/optimization/fused75/extractions")
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
    output_path: Path = _DEFAULT_OUTPUT_PATH,
    checkpoint: bool = False,
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
    for adjudication in adjudications:
        extraction_path = extraction_root / f"{adjudication.entry_id}.json"
        result = evaluate_adjudicated_entry(
            adjudication,
            extracted_items=_load_items(extraction_path),
        )
        totals.add(tp=result.metric.tp, fp=result.metric.fp, fn=result.metric.fn)

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
    report = PipelineRunReport(
        config=config,
        metric=metric,
        decision=PipelineVariantDecision(decision="checkpoint_only", reason=f"Recorded {split} variant run"),
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
    items = payload.get("items", ())
    return tuple(PipelineExtractionItem(field_id=str(item["field_id"]), value=str(item["value"])) for item in items)


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
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT_PATH)
    parser.add_argument("--checkpoint", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    """CLI entry point."""
    args = _parse_args(argv)
    run_variant(
        split=args.split,
        config_path=args.config,
        adjudication_root=args.adjudication_root,
        extraction_root=args.extraction_root,
        output_path=args.output,
        checkpoint=args.checkpoint,
    )


if __name__ == "__main__":
    main()
