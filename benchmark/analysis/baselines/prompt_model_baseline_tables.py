"""Build paper-facing tables for prompt-only frontier model baselines."""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import Any, Mapping, TypedDict, cast

from benchmark.core import REPORTS_DIR

TABLE_PROMPT_MODELS = "Prompt-only frontier model baselines"


class PromptModelRow(TypedDict):
    """One prompt-only model baseline table row."""

    baseline_id: str
    baseline_name: str
    release_cohort: str
    provider_gateway: str
    call_interface: str
    provider_family: str
    model: str
    release_date: str
    release_notes_url: str
    prompt_mode: str
    total_entries: int
    precision: float
    recall: float
    f1: float
    delta_f1_vs_ours: float
    citation_validity_rate: float | None
    hallucinated_citation_rate: float | None
    span_boundary_f1: float | None
    evidence_support_rate: float | None
    traceable_f1: float
    delta_traceable_f1_vs_ours: float
    citation_total: int
    error_rate: float
    avg_latency_s: float
    warnings: str


@dataclass(frozen=True)
class PromptModelTable:
    """Table rows plus generation metadata for prompt-only baselines."""

    generated_at: str
    rows: tuple[PromptModelRow, ...]


@dataclass(frozen=True)
class ReportPaths:
    """Paths written by the prompt-model table exporter."""

    markdown: Path
    csv: Path


def build_prompt_model_table(
    *,
    baseline_report_paths: tuple[Path, ...],
    traceability_report_paths: tuple[Path, ...],
    candidate_f1: float,
    candidate_traceable_f1: float,
) -> PromptModelTable:
    """Build a paper-facing comparison table from baseline and traceability reports."""
    traceability_by_id = {
        str(report.get("strategy_or_baseline_id") or ""): report
        for report in (_load_json_object(path) for path in traceability_report_paths)
    }
    rows: list[PromptModelRow] = []
    for path in baseline_report_paths:
        baseline_report = _load_json_object(path)
        rows.append(
            _row_from_reports(
                baseline_report=baseline_report,
                traceability_report=traceability_by_id.get(_baseline_id(baseline_report)),
                candidate_f1=candidate_f1,
                candidate_traceable_f1=candidate_traceable_f1,
            )
        )
    return PromptModelTable(generated_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"), rows=tuple(rows))


def write_prompt_model_table(table: PromptModelTable, reports_dir: Path = REPORTS_DIR) -> ReportPaths:
    """Persist prompt-only model baseline rows as Markdown and CSV."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    markdown_path = reports_dir / f"prompt_model_baseline_tables_{timestamp}.md"
    csv_path = reports_dir / f"prompt_model_baseline_tables_{timestamp}.csv"
    markdown_path.write_text(_format_markdown(table), encoding="utf-8")
    _write_csv(table, csv_path)
    return ReportPaths(markdown=markdown_path, csv=csv_path)


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint for prompt-only model baseline table generation."""
    parser = argparse.ArgumentParser(description="Build prompt-only frontier model baseline tables.")
    parser.add_argument("--candidate-f1", type=float, required=True)
    parser.add_argument("--candidate-traceable-f1", type=float, required=True)
    parser.add_argument("--baseline-reports", nargs="+", type=Path, required=True)
    parser.add_argument("--traceability-reports", nargs="+", type=Path, default=())
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    table = build_prompt_model_table(
        baseline_report_paths=tuple(args.baseline_reports),
        traceability_report_paths=tuple(args.traceability_reports),
        candidate_f1=args.candidate_f1,
        candidate_traceable_f1=args.candidate_traceable_f1,
    )
    if args.write:
        paths = write_prompt_model_table(table, reports_dir=args.reports_dir)
        print(f"MARKDOWN: {paths.markdown}")
        print(f"CSV: {paths.csv}")
    else:
        print(json.dumps({"generated_at": table.generated_at, "rows": list(table.rows)}, ensure_ascii=False, indent=2))


def _row_from_reports(
    *,
    baseline_report: Mapping[str, Any],
    traceability_report: Mapping[str, Any] | None,
    candidate_f1: float,
    candidate_traceable_f1: float,
) -> PromptModelRow:
    config = _mapping(baseline_report.get("config"))
    overall = _mapping(_mapping(baseline_report.get("aggregates")).get("overall"))
    traceability = _mapping(_mapping((traceability_report or {}).get("overall")).get("traceability"))
    counts = _mapping((traceability_report or {}).get("counts"))
    total_entries = _int(baseline_report.get("total_entries"))
    total_duration_s = _float(baseline_report.get("total_duration_s"))
    f1 = _float(overall.get("f1"))
    traceable_f1 = _float(traceability.get("traceable_f1"))
    return {
        "baseline_id": _baseline_id(baseline_report),
        "baseline_name": str(baseline_report.get("baseline_name") or ""),
        "release_cohort": str(config.get("release_cohort") or ""),
        "provider_gateway": str(config.get("provider_gateway") or ""),
        "call_interface": str(config.get("call_interface") or ""),
        "provider_family": str(config.get("provider_family") or ""),
        "model": str(config.get("model") or ""),
        "release_date": str(config.get("release_date") or ""),
        "release_notes_url": str(config.get("release_notes_url") or ""),
        "prompt_mode": str(config.get("prompt_mode") or ""),
        "total_entries": total_entries,
        "precision": _float(overall.get("precision")),
        "recall": _float(overall.get("recall")),
        "f1": f1,
        "delta_f1_vs_ours": _float(f1 - candidate_f1),
        "citation_validity_rate": _optional_float(traceability.get("citation_validity_rate")),
        "hallucinated_citation_rate": _optional_float(traceability.get("hallucinated_citation_rate")),
        "span_boundary_f1": _optional_float(traceability.get("span_boundary_f1")),
        "evidence_support_rate": _optional_float(traceability.get("evidence_support_rate")),
        "traceable_f1": traceable_f1,
        "delta_traceable_f1_vs_ours": _float(traceable_f1 - candidate_traceable_f1),
        "citation_total": _int(counts.get("citation_total")),
        "error_rate": _error_rate(baseline_report),
        "avg_latency_s": _float(total_duration_s / total_entries) if total_entries else 0.0,
        "warnings": "; ".join(str(warning) for warning in _list((traceability_report or {}).get("warnings"))),
    }


def _baseline_id(report: Mapping[str, Any]) -> str:
    return str(report.get("baseline_id") or report.get("label") or "")


def _error_rate(report: Mapping[str, Any]) -> float:
    entries = _list(report.get("per_entry"))
    if not entries:
        return 0.0
    error_count = sum(
        1
        for entry in entries
        if isinstance(entry, Mapping) and str(entry.get("pipeline_status") or "") == "error"
    )
    return _float(error_count / len(entries))


def _load_json_object(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"Expected JSON object in {path}")
    return cast(Mapping[str, Any], payload)


def _format_markdown(table: PromptModelTable) -> str:
    lines = [
        "# Prompt-Only Frontier Model Baseline Tables",
        "",
        f"Generated at: `{table.generated_at}`",
        "",
        f"## {TABLE_PROMPT_MODELS}",
    ]
    if not table.rows:
        lines.extend(["", "_No rows._"])
        return "\n".join(lines).rstrip() + "\n"
    columns = _columns(table.rows)
    lines.append("| " + " | ".join(columns) + " |")
    lines.append("| " + " | ".join("---" for _ in columns) + " |")
    for row in table.rows:
        lines.append("| " + " | ".join(_markdown_cell(row.get(column)) for column in columns) + " |")
    return "\n".join(lines).rstrip() + "\n"


def _write_csv(table: PromptModelTable, csv_path: Path) -> None:
    columns = _columns(table.rows)
    with csv_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(table.rows)


def _columns(rows: tuple[Mapping[str, object], ...]) -> list[str]:
    columns: list[str] = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    return columns


def _markdown_cell(value: object) -> str:
    if value is None:
        return ""
    return str(value).replace("|", "\\|").replace("\n", " ")


def _mapping(value: object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return cast(Mapping[str, Any], value)
    return {}


def _list(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    return []


def _int(value: object) -> int:
    if value is None or value == "":
        return 0
    return int(value)


def _float(value: object) -> float:
    if value is None or value == "":
        return 0.0
    return round(float(value), 4)


def _optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    return _float(value)


if __name__ == "__main__":
    main()
