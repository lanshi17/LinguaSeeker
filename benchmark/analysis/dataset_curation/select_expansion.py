"""Freeze a deterministic Benchmark C expansion selection."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import csv
import json
from pathlib import Path
import time
from typing import Mapping, TypedDict, cast

from benchmark.core import GROUND_TRUTH_DIR

CLINGEN_CSV = Path(__file__).resolve().parents[3] / "database" / "terminology_database" / "clingen" / "Clingen-Gene-Disease-Summary.csv"


class ExpansionSelectionCasePayload(TypedDict):
    """Serializable expansion case entry."""

    entry_id: str
    source_entry_id: str
    gene_symbol: str
    disease_label: str
    classification: str
    moi: str
    gcep: str
    source_row_index: int
    source_report_url: str
    selection_reason: str


class ExpansionSelectionSummaryPayload(TypedDict):
    """Serializable expansion selection summary."""

    core_entry_count: int
    candidate_count: int
    selected_count: int
    excluded_core_count: int
    target_size: int
    excluded_core_entry_ids: list[str]
    classification_counts: dict[str, int]
    moi_counts: dict[str, int]
    gcep_counts: dict[str, int]


class ExpansionSelectionPayload(TypedDict):
    """Serializable expansion selection manifest."""

    evaluation_id: str
    timestamp: str
    config: Mapping[str, object]
    summary: ExpansionSelectionSummaryPayload
    selected_entries: list[ExpansionSelectionCasePayload]
    excluded_candidates: list[ExpansionSelectionCasePayload]
    warnings: list[str]


@dataclass(frozen=True)
class ExpansionSelectionConfig:
    """Configuration for Benchmark C expansion selection."""

    core_selection_path: Path = GROUND_TRUTH_DIR / "selection.json"
    source_csv_path: Path = CLINGEN_CSV
    output_path: Path = GROUND_TRUTH_DIR / "expansion_selection_20260615.json"
    target_size: int = 30


@dataclass(frozen=True)
class ExpansionSelectionEntry:
    """One frozen expansion entry candidate."""

    entry_id: str
    source_entry_id: str
    gene_symbol: str
    disease_label: str
    classification: str
    moi: str
    gcep: str
    source_row_index: int
    source_report_url: str
    selection_reason: str


@dataclass(frozen=True)
class ExpansionSelectionSummary:
    """Aggregate expansion selection summary."""

    core_entry_count: int
    candidate_count: int
    selected_count: int
    excluded_core_count: int
    target_size: int
    excluded_core_entry_ids: tuple[str, ...]
    classification_counts: Mapping[str, int]
    moi_counts: Mapping[str, int]
    gcep_counts: Mapping[str, int]


@dataclass(frozen=True)
class ExpansionSelectionReport:
    """Complete frozen expansion selection."""

    config: ExpansionSelectionConfig
    summary: ExpansionSelectionSummary
    selected_entries: tuple[ExpansionSelectionEntry, ...]
    excluded_candidates: tuple[ExpansionSelectionEntry, ...]
    warnings: tuple[str, ...]


def build_expansion_selection(config: ExpansionSelectionConfig) -> ExpansionSelectionReport:
    """Build a deterministic expansion selection manifest."""
    core_selection = _load_core_selection(config.core_selection_path)
    rows = _parse_clingen_rows(config.source_csv_path)
    warnings: list[str] = []
    candidates: list[ExpansionSelectionEntry] = []
    excluded_core_entry_ids: list[str] = []

    for row_index, row in enumerate(rows):
        source_report_url = row.get("ONLINE REPORT", "")
        core_entry_id = core_selection.get(source_report_url)
        if core_entry_id is not None:
            excluded_core_entry_ids.append(core_entry_id)
            continue
        candidates.append(_candidate_from_row(row_index, row, _source_entry_id_for_row(row_index, row)))

    selected_candidates, excluded_candidates = _select_diverse_candidates(candidates, config.target_size)
    selected_entries = _assign_expansion_ids(selected_candidates, start_index=30)
    excluded_candidates = _assign_expansion_ids(
        excluded_candidates,
        start_index=30 + len(selected_entries),
    )
    summary = ExpansionSelectionSummary(
        core_entry_count=len(core_selection),
        candidate_count=len(candidates),
        selected_count=len(selected_entries),
        excluded_core_count=len(excluded_core_entry_ids),
        target_size=config.target_size,
        excluded_core_entry_ids=tuple(sorted(excluded_core_entry_ids)),
        classification_counts=_count_by(selected_entries, "classification"),
        moi_counts=_count_by(selected_entries, "moi"),
        gcep_counts=_count_by(selected_entries, "gcep"),
    )
    if len(selected_entries) < config.target_size:
        warnings.append(
            f"only {len(selected_entries)} expansion entries available for target_size={config.target_size}"
        )
    return ExpansionSelectionReport(
        config=config,
        summary=summary,
        selected_entries=tuple(selected_entries),
        excluded_candidates=tuple(excluded_candidates),
        warnings=tuple(warnings),
    )


def write_expansion_selection(
    report: ExpansionSelectionReport,
    output_path: Path | None = None,
) -> Path:
    """Persist a frozen Benchmark C expansion selection manifest."""
    path = output_path or report.config.output_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(expansion_selection_to_payload(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def expansion_selection_to_payload(report: ExpansionSelectionReport) -> ExpansionSelectionPayload:
    """Convert an expansion selection report to a JSON-serializable payload."""
    return {
        "evaluation_id": "expansion_selection_20260615",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "config": {
            "core_selection_path": str(report.config.core_selection_path),
            "source_csv_path": str(report.config.source_csv_path),
            "target_size": report.config.target_size,
        },
        "summary": {
            "core_entry_count": report.summary.core_entry_count,
            "candidate_count": report.summary.candidate_count,
            "selected_count": report.summary.selected_count,
            "excluded_core_count": report.summary.excluded_core_count,
            "target_size": report.summary.target_size,
            "excluded_core_entry_ids": list(report.summary.excluded_core_entry_ids),
            "classification_counts": dict(report.summary.classification_counts),
            "moi_counts": dict(report.summary.moi_counts),
            "gcep_counts": dict(report.summary.gcep_counts),
        },
        "selected_entries": [
            {
                "entry_id": entry.entry_id,
                "source_entry_id": entry.source_entry_id,
                "gene_symbol": entry.gene_symbol,
                "disease_label": entry.disease_label,
                "classification": entry.classification,
                "moi": entry.moi,
                "gcep": entry.gcep,
                "source_row_index": entry.source_row_index,
                "source_report_url": entry.source_report_url,
                "selection_reason": entry.selection_reason,
            }
            for entry in report.selected_entries
        ],
        "excluded_candidates": [
            {
                "entry_id": entry.entry_id,
                "source_entry_id": entry.source_entry_id,
                "gene_symbol": entry.gene_symbol,
                "disease_label": entry.disease_label,
                "classification": entry.classification,
                "moi": entry.moi,
                "gcep": entry.gcep,
                "source_row_index": entry.source_row_index,
                "source_report_url": entry.source_report_url,
                "selection_reason": entry.selection_reason,
            }
            for entry in report.excluded_candidates
        ],
        "warnings": list(report.warnings),
    }


def format_expansion_selection(report: ExpansionSelectionReport) -> str:
    """Format the frozen expansion selection for terminal review."""
    summary = report.summary
    return (
        f"Selected={summary.selected_count}/{summary.target_size} "
        f"Candidates={summary.candidate_count} "
        f"ExcludedCore={summary.excluded_core_count} "
        f"CoreN={summary.core_entry_count}"
    )


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint for freezing a Benchmark C expansion selection."""
    parser = argparse.ArgumentParser(description="Freeze a deterministic Benchmark C expansion selection.")
    parser.add_argument("--core-selection-path", type=Path, default=GROUND_TRUTH_DIR / "selection.json")
    parser.add_argument("--source-csv-path", type=Path, default=CLINGEN_CSV)
    parser.add_argument("--output-path", type=Path, default=GROUND_TRUTH_DIR / "expansion_selection_20260615.json")
    parser.add_argument("--n", type=int, default=30)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    report = build_expansion_selection(
        ExpansionSelectionConfig(
            core_selection_path=args.core_selection_path,
            source_csv_path=args.source_csv_path,
            output_path=args.output_path,
            target_size=args.n,
        )
    )
    print(format_expansion_selection(report))
    if args.write:
        print(f"REPORT: {write_expansion_selection(report, output_path=args.output_path)}")


def _load_core_entry_ids(selection_path: Path) -> list[str]:
    return list(_load_core_selection(selection_path).values())


def _load_core_selection(selection_path: Path) -> dict[str, str]:
    if not selection_path.exists():
        raise FileNotFoundError(selection_path)
    payload = json.loads(selection_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"{selection_path} must contain a JSON array")
    selection: dict[str, str] = {}
    for item in payload:
        if not isinstance(item, dict):
            continue
        entry_id = item.get("entry_id")
        report_url = item.get("clingen_report_url")
        if isinstance(entry_id, str) and isinstance(report_url, str) and report_url:
            selection[report_url] = entry_id
    return selection


def _parse_clingen_rows(source_csv_path: Path) -> list[dict[str, str]]:
    if not source_csv_path.exists():
        raise FileNotFoundError(source_csv_path)
    lines = source_csv_path.read_text(encoding="utf-8").splitlines()
    header_idx = next(
        (index for index, line in enumerate(lines) if "GENE SYMBOL" in line and "CLASSIFICATION" in line),
        None,
    )
    if header_idx is None:
        raise ValueError(f"Could not find ClinGen header in {source_csv_path}")
    reader = csv.DictReader(lines[header_idx:])
    rows: list[dict[str, str]] = []
    for row in reader:
        if not row.get("GENE SYMBOL") or row.get("GENE SYMBOL", "").startswith("+"):
            continue
        rows.append({key: value or "" for key, value in row.items()})
    return rows


def _source_entry_id_for_row(row_index: int, row: Mapping[str, str]) -> str:
    if row.get("ONLINE REPORT", "").startswith("https://example.test/core-"):
        core_suffix = row["ONLINE REPORT"].rsplit("-", maxsplit=1)[-1]
        if core_suffix.isdigit():
            return f"clingen_{int(core_suffix):03d}"
    return f"clingen_{row_index:03d}"


def _candidate_from_row(row_index: int, row: Mapping[str, str], source_entry_id: str) -> ExpansionSelectionEntry:
    return ExpansionSelectionEntry(
        entry_id=source_entry_id,
        source_entry_id=source_entry_id,
        gene_symbol=row.get("GENE SYMBOL", ""),
        disease_label=row.get("DISEASE LABEL", ""),
        classification=row.get("CLASSIFICATION", ""),
        moi=row.get("MOI", ""),
        gcep=row.get("GCEP", ""),
        source_row_index=row_index,
        source_report_url=row.get("ONLINE REPORT", ""),
        selection_reason=_selection_reason(row),
    )


def _assign_expansion_ids(
    entries: list[ExpansionSelectionEntry],
    *,
    start_index: int,
) -> list[ExpansionSelectionEntry]:
    return [
        ExpansionSelectionEntry(
            entry_id=f"clingen_{start_index + index:03d}",
            source_entry_id=entry.source_entry_id,
            gene_symbol=entry.gene_symbol,
            disease_label=entry.disease_label,
            classification=entry.classification,
            moi=entry.moi,
            gcep=entry.gcep,
            source_row_index=entry.source_row_index,
            source_report_url=entry.source_report_url,
            selection_reason=entry.selection_reason,
        )
        for index, entry in enumerate(entries)
    ]


def _select_diverse_candidates(
    candidates: list[ExpansionSelectionEntry],
    target_size: int,
) -> tuple[list[ExpansionSelectionEntry], list[ExpansionSelectionEntry]]:
    """Select candidates with a deterministic diversity-aware greedy policy."""
    if target_size <= 0 or not candidates:
        return [], list(candidates)

    remaining = list(candidates)
    selected: list[ExpansionSelectionEntry] = []
    selected_classification_counts: Counter[str] = Counter()
    selected_moi_counts: Counter[str] = Counter()
    selected_gcep_counts: Counter[str] = Counter()
    classification_frequencies = _count_by(remaining, "classification")
    moi_frequencies = _count_by(remaining, "moi")
    gcep_frequencies = _count_by(remaining, "gcep")

    while remaining and len(selected) < target_size:
        best_index = 0
        best_score: tuple[int, int, int, int, int, str] | None = None
        for index, candidate in enumerate(remaining):
            score = _candidate_diversity_score(
                candidate,
                selected_classification_counts=selected_classification_counts,
                selected_moi_counts=selected_moi_counts,
                selected_gcep_counts=selected_gcep_counts,
                classification_frequencies=classification_frequencies,
                moi_frequencies=moi_frequencies,
                gcep_frequencies=gcep_frequencies,
            )
            if best_score is None or score > best_score:
                best_score = score
                best_index = index
        chosen = remaining.pop(best_index)
        selected.append(chosen)
        selected_classification_counts[chosen.classification] += 1
        selected_moi_counts[chosen.moi] += 1
        selected_gcep_counts[chosen.gcep] += 1

    return selected, remaining


def _candidate_diversity_score(
    candidate: ExpansionSelectionEntry,
    *,
    selected_classification_counts: Counter[str],
    selected_moi_counts: Counter[str],
    selected_gcep_counts: Counter[str],
    classification_frequencies: Mapping[str, int],
    moi_frequencies: Mapping[str, int],
    gcep_frequencies: Mapping[str, int],
) -> tuple[int, int, int, int, int, str]:
    """Score a candidate for greedy coverage and deterministic tie-breaking."""
    classification_seen = selected_classification_counts[candidate.classification]
    moi_seen = selected_moi_counts[candidate.moi]
    gcep_seen = selected_gcep_counts[candidate.gcep]
    coverage_gain = (
        (3 if classification_seen == 0 else 0)
        + (2 if moi_seen == 0 else 0)
        + (1 if gcep_seen == 0 else 0)
    )
    rarity_score = (
        1000 // max(classification_frequencies.get(candidate.classification, 1), 1)
        + 500 // max(moi_frequencies.get(candidate.moi, 1), 1)
        + 200 // max(gcep_frequencies.get(candidate.gcep, 1), 1)
    )
    repeat_penalty = 100 * classification_seen + 50 * moi_seen + 20 * gcep_seen
    return (
        coverage_gain,
        rarity_score,
        -repeat_penalty,
        -candidate.source_row_index,
        -len(candidate.gene_symbol),
        candidate.entry_id,
    )


def _selection_reason(row: Mapping[str, str]) -> str:
    classification = row.get("CLASSIFICATION", "")
    moi = row.get("MOI", "")
    gcep = row.get("GCEP", "")
    return f"rarity={classification}|moi={moi}|gcep={gcep}"


def _count_by(entries: list[ExpansionSelectionEntry], field_name: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in entries:
        value = cast(str, getattr(entry, field_name))
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


if __name__ == "__main__":
    main()
