"""Build a Benchmark B multilingual Phase 2 queue from frozen source manifests."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import Any, Mapping, TypedDict, cast

from benchmark.core import GROUND_TRUTH_DIR, REPORTS_DIR


MAIN_MULTILINGUAL_LANGUAGES = ("ja", "ko", "zh")
DEFAULT_PILOT_SELECTION_PATH = GROUND_TRUTH_DIR / "benchmark_b_pilot_selection.json"
DEFAULT_OUTPUT_PATH = GROUND_TRUTH_DIR / "benchmark_b_phase2_queue.json"


class BenchmarkBPhase2QueueItemPayload(TypedDict):
    """Serializable queue item for one multilingual source PDF."""

    queue_id: str
    entry_id: str
    article_language: str
    target_gene: str
    target_disease: str
    source_id: str
    source_database: str
    source_url: str | None
    local_path: str
    source_pdf_path: str
    sha256: str | None
    annotation_status: str
    access_status: str
    benchmark_layer: str
    literature_type: str


class BenchmarkBPhase2QueueSummaryPayload(TypedDict):
    """Serializable Benchmark B queue summary."""

    selected_case_count: int
    ready_source_count: int
    by_language: Mapping[str, int]
    missing_language_by_entry: Mapping[str, list[str]]


class BenchmarkBPhase2QueuePayload(TypedDict):
    """Serializable Benchmark B Phase 2 queue manifest."""

    evaluation_id: str
    timestamp: str
    config: Mapping[str, object]
    summary: BenchmarkBPhase2QueueSummaryPayload
    items: list[BenchmarkBPhase2QueueItemPayload]
    warnings: list[str]


@dataclass(frozen=True)
class BenchmarkBPhase2QueueConfig:
    """Configuration for Benchmark B Phase 2 queue generation."""

    selection_path: Path = GROUND_TRUTH_DIR / "selection.json"
    pilot_selection_path: Path = DEFAULT_PILOT_SELECTION_PATH
    source_inventory_path: Path | None = None
    output_path: Path = DEFAULT_OUTPUT_PATH
    allowed_languages: tuple[str, ...] = MAIN_MULTILINGUAL_LANGUAGES


@dataclass(frozen=True)
class BenchmarkBPhase2QueueItem:
    """One source PDF ready to be submitted to Phase 2 for Benchmark B."""

    queue_id: str
    entry_id: str
    article_language: str
    target_gene: str
    target_disease: str
    source_id: str
    source_database: str
    source_url: str | None
    local_path: str
    source_pdf_path: Path
    sha256: str | None
    annotation_status: str
    access_status: str
    benchmark_layer: str
    literature_type: str


@dataclass(frozen=True)
class BenchmarkBPhase2QueueSummary:
    """Aggregate queue status for the selected Benchmark B pilot."""

    selected_case_count: int
    ready_source_count: int
    by_language: Mapping[str, int]
    missing_language_by_entry: Mapping[str, tuple[str, ...]]


@dataclass(frozen=True)
class BenchmarkBPhase2QueueReport:
    """Complete Benchmark B Phase 2 queue manifest."""

    config: BenchmarkBPhase2QueueConfig
    summary: BenchmarkBPhase2QueueSummary
    items: tuple[BenchmarkBPhase2QueueItem, ...]
    warnings: tuple[str, ...]


def build_benchmark_b_phase2_queue(config: BenchmarkBPhase2QueueConfig) -> BenchmarkBPhase2QueueReport:
    """Build the multilingual source queue for the frozen Benchmark B pilot."""
    source_inventory_path = config.source_inventory_path or _latest_source_inventory_report(REPORTS_DIR)
    selection_by_id = _selection_by_id(config.selection_path)
    pilot_entry_languages = _pilot_entry_languages(config.pilot_selection_path, config.allowed_languages)
    inventory = _load_inventory(source_inventory_path)
    repo_root = _repo_root_from_inventory(inventory, source_inventory_path)
    records = _queue_candidate_records(inventory, config.allowed_languages)

    items: list[BenchmarkBPhase2QueueItem] = []
    warnings: list[str] = []
    available_by_entry: dict[str, set[str]] = {entry_id: set() for entry_id in pilot_entry_languages}

    for record in records:
        entry_id = _entry_id_from_local_path(_required_str(record, "local_path"))
        if not entry_id or entry_id not in pilot_entry_languages:
            continue
        article_language = _required_str(record, "article_language").casefold()
        if article_language not in pilot_entry_languages[entry_id]:
            continue
        selection = selection_by_id.get(entry_id)
        if selection is None:
            warnings.append(f"{entry_id}: missing target metadata in {config.selection_path}")
            continue
        local_path = _required_str(record, "local_path")
        source_pdf_path = _source_pdf_path(repo_root, record, local_path)
        available_by_entry[entry_id].add(article_language)
        items.append(
            BenchmarkBPhase2QueueItem(
                queue_id=f"{entry_id}:{article_language}",
                entry_id=entry_id,
                article_language=article_language,
                target_gene=str(selection.get("gene_symbol", "")),
                target_disease=str(selection.get("disease_label", "")),
                source_id=_required_str(record, "source_id"),
                source_database=_required_str(record, "source_database"),
                source_url=_optional_str(record.get("source_url")),
                local_path=local_path,
                source_pdf_path=source_pdf_path,
                sha256=_optional_str(record.get("sha256")),
                annotation_status=_required_str(record, "annotation_status"),
                access_status=_required_str(record, "access_status"),
                benchmark_layer=_required_str(record, "benchmark_layer"),
                literature_type=_required_str(record, "literature_type"),
            )
        )

    items.sort(key=lambda item: (item.entry_id, item.article_language, item.local_path))
    missing = {
        entry_id: tuple(language for language in expected if language not in available_by_entry[entry_id])
        for entry_id, expected in pilot_entry_languages.items()
    }
    missing = {entry_id: languages for entry_id, languages in missing.items() if languages}
    summary = BenchmarkBPhase2QueueSummary(
        selected_case_count=len(pilot_entry_languages),
        ready_source_count=len(items),
        by_language=_count_by_language(items),
        missing_language_by_entry=dict(sorted(missing.items())),
    )
    return BenchmarkBPhase2QueueReport(
        config=config,
        summary=summary,
        items=tuple(items),
        warnings=tuple(warnings),
    )


def write_benchmark_b_phase2_queue(
    report: BenchmarkBPhase2QueueReport,
    output_path: Path | None = None,
) -> Path:
    """Persist a Benchmark B Phase 2 queue manifest."""
    path = output_path or report.config.output_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(benchmark_b_phase2_queue_to_payload(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def benchmark_b_phase2_queue_to_payload(report: BenchmarkBPhase2QueueReport) -> BenchmarkBPhase2QueuePayload:
    """Convert a queue report to a JSON-serializable payload."""
    source_inventory_path = report.config.source_inventory_path or _latest_source_inventory_report(REPORTS_DIR)
    return {
        "evaluation_id": "benchmark_b_phase2_queue",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "config": {
            "selection_path": str(report.config.selection_path),
            "pilot_selection_path": str(report.config.pilot_selection_path),
            "source_inventory_path": str(source_inventory_path),
            "allowed_languages": list(report.config.allowed_languages),
        },
        "summary": {
            "selected_case_count": report.summary.selected_case_count,
            "ready_source_count": report.summary.ready_source_count,
            "by_language": dict(report.summary.by_language),
            "missing_language_by_entry": {
                entry_id: list(languages)
                for entry_id, languages in report.summary.missing_language_by_entry.items()
            },
        },
        "items": [
            {
                "queue_id": item.queue_id,
                "entry_id": item.entry_id,
                "article_language": item.article_language,
                "target_gene": item.target_gene,
                "target_disease": item.target_disease,
                "source_id": item.source_id,
                "source_database": item.source_database,
                "source_url": item.source_url,
                "local_path": item.local_path,
                "source_pdf_path": str(item.source_pdf_path),
                "sha256": item.sha256,
                "annotation_status": item.annotation_status,
                "access_status": item.access_status,
                "benchmark_layer": item.benchmark_layer,
                "literature_type": item.literature_type,
            }
            for item in report.items
        ],
        "warnings": list(report.warnings),
    }


def format_benchmark_b_phase2_queue(report: BenchmarkBPhase2QueueReport) -> str:
    """Format queue status for terminal review."""
    return (
        f"QueuedSources={report.summary.ready_source_count} "
        f"SelectedCases={report.summary.selected_case_count} "
        f"MissingCases={len(report.summary.missing_language_by_entry)} "
        f"ByLanguage={dict(report.summary.by_language)}"
    )


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint for Benchmark B Phase 2 queue generation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection-path", type=Path, default=GROUND_TRUTH_DIR / "selection.json")
    parser.add_argument("--pilot-selection-path", type=Path, default=DEFAULT_PILOT_SELECTION_PATH)
    parser.add_argument("--source-inventory-path", type=Path, default=None)
    parser.add_argument("--output-path", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--allowed-languages", nargs="*", default=list(MAIN_MULTILINGUAL_LANGUAGES))
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    report = build_benchmark_b_phase2_queue(
        BenchmarkBPhase2QueueConfig(
            selection_path=args.selection_path,
            pilot_selection_path=args.pilot_selection_path,
            source_inventory_path=args.source_inventory_path,
            output_path=args.output_path,
            allowed_languages=tuple(args.allowed_languages),
        )
    )
    print(format_benchmark_b_phase2_queue(report))
    if args.write:
        print(f"REPORT: {write_benchmark_b_phase2_queue(report)}")


def _latest_source_inventory_report(reports_dir: Path) -> Path:
    candidates = sorted(reports_dir.glob("source_inventory_*.json"))
    if not candidates:
        raise FileNotFoundError(f"No source_inventory_*.json report found under {reports_dir}")
    return candidates[-1]


def _selection_by_id(selection_path: Path) -> Mapping[str, Mapping[str, Any]]:
    payload = _load_json_object(selection_path)
    if not isinstance(payload, list):
        raise ValueError(f"Expected list in {selection_path}")
    return {
        str(item["entry_id"]): cast(Mapping[str, Any], item)
        for item in payload
        if isinstance(item, Mapping) and item.get("entry_id")
    }


def _pilot_entry_languages(
    pilot_selection_path: Path,
    allowed_languages: tuple[str, ...],
) -> Mapping[str, tuple[str, ...]]:
    payload = _load_json_object(pilot_selection_path)
    selected_cases = payload.get("selected_cases")
    if not isinstance(selected_cases, list):
        raise ValueError(f"Expected selected_cases list in {pilot_selection_path}")
    allowed = {language.casefold() for language in allowed_languages}
    entry_languages: dict[str, tuple[str, ...]] = {}
    for case in selected_cases:
        if not isinstance(case, Mapping):
            continue
        entry_id = str(case.get("entry_id", ""))
        languages = case.get("source_languages")
        if not entry_id or not isinstance(languages, list):
            continue
        entry_languages[entry_id] = tuple(
            sorted({str(language).casefold() for language in languages if str(language).casefold() in allowed})
        )
    return entry_languages


def _load_inventory(source_inventory_path: Path) -> Mapping[str, Any]:
    payload = _load_json_object(source_inventory_path)
    if not isinstance(payload, Mapping):
        raise ValueError(f"Expected object in {source_inventory_path}")
    return payload


def _repo_root_from_inventory(inventory: Mapping[str, Any], source_inventory_path: Path) -> Path:
    config = inventory.get("config")
    if isinstance(config, Mapping):
        repo_root = _optional_str(config.get("repo_root"))
        if repo_root:
            return Path(repo_root)
    return source_inventory_path.resolve().parents[3]


def _queue_candidate_records(
    inventory: Mapping[str, Any],
    allowed_languages: tuple[str, ...],
) -> list[Mapping[str, Any]]:
    records = inventory.get("records")
    if not isinstance(records, list):
        return []
    allowed = {language.casefold() for language in allowed_languages}
    candidates: list[Mapping[str, Any]] = []
    for record in records:
        if not isinstance(record, Mapping):
            continue
        if record.get("source_kind") != "raw_pdf":
            continue
        if str(record.get("article_language", "")).casefold() not in allowed:
            continue
        if str(record.get("literature_type", "")) != "case_report":
            continue
        if not _entry_id_from_local_path(str(record.get("local_path", ""))):
            continue
        candidates.append(cast(Mapping[str, Any], record))
    return candidates


def _entry_id_from_local_path(local_path: str) -> str:
    path = Path(local_path)
    if path.suffix.casefold() != ".pdf":
        return ""
    if len(path.parts) < 2 or path.parts[-2] != "case_report":
        return ""
    stem = path.stem
    return stem if stem.startswith("clingen_") else ""


def _source_pdf_path(repo_root: Path, record: Mapping[str, Any], local_path: str) -> Path:
    raw_path = _optional_str(record.get("source_pdf_path"))
    if raw_path:
        candidate = Path(raw_path)
        if candidate.exists():
            return candidate
    path = Path(local_path)
    return path if path.is_absolute() else repo_root / path


def _count_by_language(items: list[BenchmarkBPhase2QueueItem]) -> Mapping[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item.article_language] = counts.get(item.article_language, 0) + 1
    return dict(sorted(counts.items()))


def _required_str(record: Mapping[str, Any], key: str) -> str:
    value = _optional_str(record.get(key))
    if value is None:
        return ""
    return value


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _load_json_object(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
