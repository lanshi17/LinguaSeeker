"""Freeze a multilingual Benchmark B pilot from the Layer 3 source corpus."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import Mapping, TypedDict

from benchmark.layer3.evaluate import GROUND_TRUTH_DIR

SOURCE_CORPUS_ROOT = Path(__file__).resolve().parents[2] / "pipeline" / "input" / "ground_truth"


class BenchmarkBPilotSourceFilePayload(TypedDict):
    """Serializable source file entry."""

    language: str
    path: str


class BenchmarkBPilotCasePayload(TypedDict):
    """Serializable multilingual pilot case."""

    entry_id: str
    source_languages: list[str]
    source_files: list[BenchmarkBPilotSourceFilePayload]
    non_english_source_count: int


class BenchmarkBPilotSummaryPayload(TypedDict):
    """Serializable pilot summary."""

    total_frozen_entries: int
    eligible_count: int
    selected_count: int
    excluded_english_only_count: int
    target_size: int
    excluded_english_only_entry_ids: list[str]


class BenchmarkBPilotSelectionPayload(TypedDict):
    """Serializable Benchmark B pilot manifest."""

    evaluation_id: str
    timestamp: str
    config: Mapping[str, object]
    summary: BenchmarkBPilotSummaryPayload
    selected_cases: list[BenchmarkBPilotCasePayload]
    warnings: list[str]


@dataclass(frozen=True)
class BenchmarkBPilotSelectionConfig:
    """Configuration for Benchmark B pilot freezing."""

    selection_path: Path = GROUND_TRUTH_DIR / "selection.json"
    source_corpus_root: Path = SOURCE_CORPUS_ROOT
    output_path: Path = GROUND_TRUTH_DIR / "benchmark_b_pilot_selection.json"
    target_size: int = 10


@dataclass(frozen=True)
class BenchmarkBPilotSourceFile:
    """One source PDF backing a multilingual pilot case."""

    language: str
    path: Path


@dataclass(frozen=True)
class BenchmarkBPilotCase:
    """One frozen pilot case with its source-language coverage."""

    entry_id: str
    source_languages: tuple[str, ...]
    source_files: tuple[BenchmarkBPilotSourceFile, ...]
    non_english_source_count: int


@dataclass(frozen=True)
class BenchmarkBPilotSummary:
    """Aggregate Benchmark B pilot summary."""

    total_frozen_entries: int
    eligible_count: int
    selected_count: int
    excluded_english_only_count: int
    target_size: int
    excluded_english_only_entry_ids: tuple[str, ...]


@dataclass(frozen=True)
class BenchmarkBPilotSelectionReport:
    """Complete frozen Benchmark B pilot selection."""

    config: BenchmarkBPilotSelectionConfig
    summary: BenchmarkBPilotSummary
    selected_cases: tuple[BenchmarkBPilotCase, ...]
    warnings: tuple[str, ...]


def build_benchmark_b_pilot_selection(
    config: BenchmarkBPilotSelectionConfig,
) -> BenchmarkBPilotSelectionReport:
    """Build a deterministic multilingual pilot selection."""
    entry_ids = _entry_ids(config.selection_path)
    eligible_cases: list[BenchmarkBPilotCase] = []
    excluded_english_only_entry_ids: list[str] = []
    warnings: list[str] = []

    for entry_id in entry_ids:
        source_files = _source_files_for_entry(entry_id, config.source_corpus_root)
        if not source_files:
            warnings.append(f"{entry_id}: no source PDFs found in {config.source_corpus_root}")
            continue

        source_languages = tuple(sorted(file.language for file in source_files))
        non_english_source_count = sum(1 for file in source_files if file.language != "en")
        if non_english_source_count <= 0:
            excluded_english_only_entry_ids.append(entry_id)
            continue

        eligible_cases.append(
            BenchmarkBPilotCase(
                entry_id=entry_id,
                source_languages=source_languages,
                source_files=tuple(source_files),
                non_english_source_count=non_english_source_count,
            )
        )

    eligible_cases.sort(key=lambda case: (-case.non_english_source_count, case.entry_id))
    selected_cases = eligible_cases[: config.target_size]

    summary = BenchmarkBPilotSummary(
        total_frozen_entries=len(entry_ids),
        eligible_count=len(eligible_cases),
        selected_count=len(selected_cases),
        excluded_english_only_count=len(excluded_english_only_entry_ids),
        target_size=config.target_size,
        excluded_english_only_entry_ids=tuple(excluded_english_only_entry_ids),
    )
    return BenchmarkBPilotSelectionReport(
        config=config,
        summary=summary,
        selected_cases=tuple(selected_cases),
        warnings=tuple(warnings),
    )


def write_benchmark_b_pilot_selection(
    report: BenchmarkBPilotSelectionReport,
    output_path: Path | None = None,
) -> Path:
    """Persist a frozen Benchmark B pilot selection manifest."""
    path = output_path or report.config.output_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(benchmark_b_pilot_selection_to_payload(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def benchmark_b_pilot_selection_to_payload(
    report: BenchmarkBPilotSelectionReport,
) -> BenchmarkBPilotSelectionPayload:
    """Convert a pilot selection report to a JSON-serializable payload."""
    return {
        "evaluation_id": "benchmark_b_pilot_selection",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "config": {
            "selection_path": str(report.config.selection_path),
            "source_corpus_root": str(report.config.source_corpus_root),
            "target_size": report.config.target_size,
        },
        "summary": {
            "total_frozen_entries": report.summary.total_frozen_entries,
            "eligible_count": report.summary.eligible_count,
            "selected_count": report.summary.selected_count,
            "excluded_english_only_count": report.summary.excluded_english_only_count,
            "target_size": report.summary.target_size,
            "excluded_english_only_entry_ids": list(report.summary.excluded_english_only_entry_ids),
        },
        "selected_cases": [
            {
                "entry_id": case.entry_id,
                "source_languages": list(case.source_languages),
                "source_files": [
                    {"language": source_file.language, "path": str(source_file.path)}
                    for source_file in case.source_files
                ],
                "non_english_source_count": case.non_english_source_count,
            }
            for case in report.selected_cases
        ],
        "warnings": list(report.warnings),
    }


def format_benchmark_b_pilot_selection(report: BenchmarkBPilotSelectionReport) -> str:
    """Format the frozen pilot selection for terminal review."""
    summary = report.summary
    return (
        f"PilotSelected={summary.selected_count}/{summary.target_size} "
        f"Eligible={summary.eligible_count} "
        f"ExcludedEnglishOnly={summary.excluded_english_only_count} "
        f"N={summary.total_frozen_entries}"
    )


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint for freezing a Benchmark B pilot."""
    parser = argparse.ArgumentParser(description="Freeze a multilingual Benchmark B pilot selection.")
    parser.add_argument("--selection-path", type=Path, default=GROUND_TRUTH_DIR / "selection.json")
    parser.add_argument("--source-corpus-root", type=Path, default=SOURCE_CORPUS_ROOT)
    parser.add_argument("--output-path", type=Path, default=GROUND_TRUTH_DIR / "benchmark_b_pilot_selection.json")
    parser.add_argument("--target-size", type=int, default=10)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    report = build_benchmark_b_pilot_selection(
        BenchmarkBPilotSelectionConfig(
            selection_path=args.selection_path,
            source_corpus_root=args.source_corpus_root,
            output_path=args.output_path,
            target_size=args.target_size,
        )
    )
    print(format_benchmark_b_pilot_selection(report))
    if args.write:
        print(f"REPORT: {write_benchmark_b_pilot_selection(report, output_path=args.output_path)}")


def _entry_ids(selection_path: Path) -> tuple[str, ...]:
    if not selection_path.exists():
        raise FileNotFoundError(selection_path)
    payload = json.loads(selection_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Expected list in {selection_path}")
    entry_ids = [
        str(item.get("entry_id", ""))
        for item in payload
        if isinstance(item, Mapping) and item.get("entry_id")
    ]
    if not entry_ids:
        raise ValueError(f"No entry_id values found in {selection_path}")
    return tuple(entry_ids)


def _source_files_for_entry(entry_id: str, source_corpus_root: Path) -> list[BenchmarkBPilotSourceFile]:
    source_files: list[BenchmarkBPilotSourceFile] = []
    if not source_corpus_root.exists():
        return source_files

    for language_dir in sorted(
        (path for path in source_corpus_root.iterdir() if path.is_dir()),
        key=lambda path: path.name,
    ):
        pdf_path = language_dir / "case_report" / f"{entry_id}.pdf"
        if pdf_path.exists():
            source_files.append(BenchmarkBPilotSourceFile(language=language_dir.name, path=pdf_path))
    return source_files


if __name__ == "__main__":
    main()
