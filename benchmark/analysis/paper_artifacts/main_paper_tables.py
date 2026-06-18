"""Build reviewer-facing BIBM Main Paper tables from frozen reports."""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import Any, Mapping, TypedDict, cast

from benchmark.core import REPORTS_DIR

TABLE_DATASET = "Table 1 Dataset composition"
TABLE_MAIN = "Table 2 Main method vs baselines"
TABLE_ABLATION = "Table 3 Ablation study"
TABLE_TRACEABILITY = "Table 4 Traceability metrics"
TABLE_ERRORS = "Table 5 Error breakdown"
TABLE_READINESS = "Table 6 Benchmark readiness and pilot selection"
TABLE_ALIGNMENT = "Table 7 Alignment and drift/conflict detection"
TABLE_AUGMENTATION = "Table 8 Evidence augmentation metrics"

ERROR_ROOT_CAUSE_ORDER = (
    "wrong_relationship_semantics",
    "disease_boundary_error",
    "candidate_absent",
    "source_invalid_or_unscorable",
    "non_target_contamination",
    "score_ranking_error",
    "threshold_or_margin_error",
    "table_or_caption_recall_error",
    "evaluation_normalization_gap",
)


class MainPaperTablesPayload(TypedDict):
    """Serializable Main Paper table bundle."""

    generated_at: str
    manifest_path: str
    tables: Mapping[str, list[Mapping[str, object]]]


@dataclass(frozen=True)
class MainPaperTable:
    """One named table and its row payloads."""

    title: str
    rows: tuple[Mapping[str, object], ...]


@dataclass(frozen=True)
class MainPaperTables:
    """Reviewer-facing table bundle generated from one frozen manifest."""

    generated_at: str
    manifest_path: Path
    tables: tuple[MainPaperTable, ...]


@dataclass(frozen=True)
class ReportPaths:
    """Paths written by the Main Paper table exporter."""

    markdown: Path
    csv: Path


def build_main_paper_tables(manifest_path: Path) -> MainPaperTables:
    """Build the six reviewer-facing Main Paper tables from a frozen manifest."""
    manifest = _load_json_object(manifest_path)
    return MainPaperTables(
        generated_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        manifest_path=manifest_path,
        tables=(
            MainPaperTable(TABLE_DATASET, _dataset_rows(manifest)),
            MainPaperTable(TABLE_MAIN, _main_method_rows(manifest)),
            MainPaperTable(TABLE_ABLATION, _ablation_rows(manifest)),
            MainPaperTable(TABLE_TRACEABILITY, _traceability_rows(manifest, manifest_path=manifest_path)),
            MainPaperTable(TABLE_ERRORS, _error_rows(manifest, manifest_path=manifest_path)),
            MainPaperTable(TABLE_READINESS, _readiness_rows(manifest)),
            MainPaperTable(TABLE_ALIGNMENT, _alignment_rows(manifest_path)),
            MainPaperTable(TABLE_AUGMENTATION, _augmentation_rows(manifest_path)),
        ),
    )


def main_paper_tables_to_payload(tables: MainPaperTables) -> MainPaperTablesPayload:
    """Convert Main Paper tables into a JSON-serializable payload."""
    return {
        "generated_at": tables.generated_at,
        "manifest_path": str(tables.manifest_path),
        "tables": {table.title: list(table.rows) for table in tables.tables},
    }


def write_main_paper_tables(tables: MainPaperTables, reports_dir: Path = REPORTS_DIR) -> ReportPaths:
    """Persist Main Paper tables as Markdown and CSV."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    markdown_path = reports_dir / f"main_paper_tables_{timestamp}.md"
    csv_path = reports_dir / f"main_paper_tables_{timestamp}.csv"
    markdown_path.write_text(_format_markdown(tables), encoding="utf-8")
    _write_csv(tables, csv_path)
    return ReportPaths(markdown=markdown_path, csv=csv_path)


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint for Main Paper table generation."""
    parser = argparse.ArgumentParser(description="Build BIBM Main Paper tables from a frozen manifest.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    tables = build_main_paper_tables(args.manifest)
    if args.write:
        report_paths = write_main_paper_tables(tables, reports_dir=args.reports_dir)
        print(f"MARKDOWN: {report_paths.markdown}")
        print(f"CSV: {report_paths.csv}")
    else:
        print(json.dumps(main_paper_tables_to_payload(tables), ensure_ascii=False, indent=2))


def _dataset_rows(manifest: Mapping[str, Any]) -> tuple[Mapping[str, object], ...]:
    coverage = _mapping(manifest.get("coverage"))
    reproducibility = _mapping(manifest.get("reproducibility"))
    source_reports = _mapping(manifest.get("source_reports"))
    source_inventory_summary = _mapping(manifest.get("source_inventory_summary"))
    entry_ids = _list(reproducibility.get("entry_ids"))
    return (
        {
            "total_entries": _int(coverage.get("total_entries")),
            "covered_count": _int(coverage.get("covered_count")),
            "needs_pipeline_count": _int(coverage.get("needs_pipeline_count")),
            "frozen_entry_count": len(entry_ids),
            "benchmark_a_readiness_status": _readiness_status(source_reports.get("benchmark_a_readiness_report")),
            "benchmark_b_pilot_selection_status": _readiness_status(source_reports.get("benchmark_b_pilot_selection_report")),
            "git_commit": str(reproducibility.get("git_commit") or manifest.get("git_commit") or ""),
            "ablation_report": str(source_reports.get("ablation_report") or ""),
            "clinvar_fused_entry_count": _int(source_inventory_summary.get("clinvar_fused_entry_count")),
            "main_multilingual_pdf_count": _int(source_inventory_summary.get("main_multilingual_pdf_count")),
        },
    )


def _main_method_rows(manifest: Mapping[str, Any]) -> tuple[Mapping[str, object], ...]:
    rows: list[Mapping[str, object]] = []
    for baseline in _list(manifest.get("baselines")):
        if not isinstance(baseline, Mapping):
            continue
        rows.append(
            {
                "method": str(baseline.get("label") or "baseline"),
                "role": "baseline",
                "total_entries": _int(baseline.get("total_entries")),
                "precision": _float(baseline.get("precision")),
                "recall": _float(baseline.get("recall")),
                "f1": _float(baseline.get("f1")),
            }
        )

    g2_statistics = _mapping(manifest.get("g2_statistics"))
    candidate_strategy = str(g2_statistics.get("candidate_strategy") or "context_verifier_reconcile")
    candidate = _strategy_by_name(manifest, candidate_strategy)
    rows.append(
        {
            "method": candidate_strategy,
            "role": "ours",
            "total_entries": _int(candidate.get("total_entries") or g2_statistics.get("sample_size")),
            "precision": _float(candidate.get("precision")),
            "recall": _float(candidate.get("recall")),
            "f1": _float(candidate.get("f1") or g2_statistics.get("candidate_f1")),
            "delta_f1_vs_grounded_hard_rule": _float(g2_statistics.get("delta_f1")),
            "sign_test_p": _float(g2_statistics.get("sign_test_p")),
            "main_paper_ready": bool(g2_statistics.get("main_paper_ready", False)),
        }
    )
    return tuple(rows)


def _ablation_rows(manifest: Mapping[str, Any]) -> tuple[Mapping[str, object], ...]:
    rows: list[Mapping[str, object]] = []
    for strategy in _list(manifest.get("strategies")):
        if not isinstance(strategy, Mapping):
            continue
        rows.append(
            {
                "strategy": str(strategy.get("strategy") or ""),
                "total_entries": _int(strategy.get("total_entries")),
                "precision": _float(strategy.get("precision")),
                "recall": _float(strategy.get("recall")),
                "f1": _float(strategy.get("f1")),
            }
        )
    return tuple(rows)


def _traceability_rows(
    manifest: Mapping[str, Any],
    *,
    manifest_path: Path,
) -> tuple[Mapping[str, object], ...]:
    traceability_payload = _load_optional_traceability_report(manifest, manifest_path=manifest_path)
    if traceability_payload:
        return (_traceability_row_from_report(traceability_payload),)

    g2_statistics = _mapping(manifest.get("g2_statistics"))
    candidate_strategy = str(g2_statistics.get("candidate_strategy") or "context_verifier_reconcile")
    return (
        {
            "strategy_or_baseline_id": candidate_strategy,
            "citation_validity_rate": None,
            "hallucinated_citation_rate": None,
            "span_boundary_f1": None,
            "evidence_support_rate": None,
            "traceable_f1": _float(g2_statistics.get("candidate_f1")),
            "cross_lingual_consistency": None,
        },
    )


def _error_rows(
    manifest: Mapping[str, Any],
    *,
    manifest_path: Path,
) -> tuple[Mapping[str, object], ...]:
    diagnosis_payload = _load_optional_diagnosis_report(manifest, manifest_path=manifest_path)
    if diagnosis_payload:
        summary = _mapping(diagnosis_payload.get("summary"))
        by_root_cause = _mapping(summary.get("by_root_cause"))
        rows = [
            {
                "root_cause": root_cause,
                "error_count": _int(count),
                "strategy": str(diagnosis_payload.get("strategy") or ""),
                "source_report": str(diagnosis_payload.get("report_path") or ""),
            }
            for root_cause, count in by_root_cause.items()
        ]
        return tuple(sorted(rows, key=lambda row: (-_int(row.get("error_count")), _root_cause_rank(row))))

    return tuple(
        {
            "root_cause": root_cause,
            "error_count": 0,
            "strategy": str(_mapping(manifest.get("g2_statistics")).get("candidate_strategy") or ""),
            "source_report": "",
        }
        for root_cause in ERROR_ROOT_CAUSE_ORDER
    )


def _readiness_rows(manifest: Mapping[str, Any]) -> tuple[Mapping[str, object], ...]:
    source_reports = _mapping(manifest.get("source_reports"))
    readiness_report = str(source_reports.get("benchmark_a_readiness_report") or "")
    pilot_report = str(source_reports.get("benchmark_b_pilot_selection_report") or "")
    return (
        {
            "artifact": "Benchmark A readiness",
            "status": _readiness_status(readiness_report),
            "report_path": readiness_report,
            "note": "Alignment annotations are required before Benchmark A metrics are reportable.",
        },
        {
            "artifact": "Benchmark B pilot selection",
            "status": _readiness_status(pilot_report),
            "report_path": pilot_report,
            "note": "Multilingual pilot selection is frozen from the existing non-English corpus.",
        },
    )


def _latest_report(manifest_path: Path, pattern: str) -> Mapping[str, Any] | None:
    reports_dir = manifest_path.parent
    candidates = sorted(reports_dir.glob(pattern))
    if not candidates:
        return None
    return _load_json_object(candidates[-1])


def _alignment_rows(manifest_path: Path) -> tuple[Mapping[str, object], ...]:
    payload = _latest_report(manifest_path, "alignment_metrics_*.json")
    if not payload:
        return (
            {
                "scope": "overall",
                "alignment_accuracy": None,
                "support_accuracy": None,
                "drift_detection_f1": None,
                "conflict_detection_f1": None,
                "N": 0,
            },
        )
    overall = _mapping(_mapping(payload.get("overall")).get("alignment"))
    counts = _mapping(payload.get("counts"))
    rows: list[Mapping[str, object]] = [
        {
            "scope": "overall",
            "alignment_accuracy": _optional_float(overall.get("alignment_accuracy")),
            "support_accuracy": _optional_float(overall.get("support_label_accuracy")),
            "drift_detection_f1": _optional_float(overall.get("drift_detection_f1")),
            "conflict_detection_f1": _optional_float(overall.get("conflict_detection_f1")),
            "N": _int(counts.get("total")),
        }
    ]
    by_field = _mapping(payload.get("by_field"))
    for field_id in sorted(by_field):
        field_alignment = _mapping(_mapping(by_field[field_id]).get("alignment"))
        rows.append(
            {
                "scope": field_id,
                "alignment_accuracy": _optional_float(field_alignment.get("alignment_accuracy")),
                "support_accuracy": _optional_float(field_alignment.get("support_label_accuracy")),
                "drift_detection_f1": _optional_float(field_alignment.get("drift_detection_f1")),
                "conflict_detection_f1": _optional_float(field_alignment.get("conflict_detection_f1")),
                "N": "",
            }
        )
    return tuple(rows)


def _augmentation_rows(manifest_path: Path) -> tuple[Mapping[str, object], ...]:
    payload = _latest_report(manifest_path, "evidence_augmentation_metrics_*.json")
    if not payload:
        return (
            {
                "scope": "overall",
                "evidence_coverage_gain": None,
                "non_english_evidence_yield": None,
                "unique_evidence_gain": None,
                "traceable_augmentation_rate": None,
                "interpretation_relevant_evidence_gain": None,
                "reviewer_burden": None,
                "N": 0,
            },
        )
    overall = _mapping(payload.get("overall"))
    total_cases = len(_list(payload.get("per_case")))
    augmented_cases = sum(
        1
        for case in _list(payload.get("per_case"))
        if _int(_mapping(case.get("matrix")).get("non_english_added_evidence_count")) > 0
    )
    return (
        {
            "scope": "overall",
            "evidence_coverage_gain": _optional_float(overall.get("evidence_coverage_gain")),
            "non_english_evidence_yield": _optional_float(overall.get("non_english_evidence_yield")),
            "unique_evidence_gain": _int(overall.get("unique_evidence_gain")),
            "traceable_augmentation_rate": _optional_float(overall.get("traceable_augmentation_rate")),
            "interpretation_relevant_evidence_gain": _optional_float(overall.get("interpretation_relevant_evidence_gain")),
            "reviewer_burden": _optional_float(overall.get("reviewer_burden")),
            "N": total_cases,
        },
        {
            "scope": f"augmented_cases ({augmented_cases})",
            "evidence_coverage_gain": "",
            "non_english_evidence_yield": "",
            "unique_evidence_gain": "",
            "traceable_augmentation_rate": "",
            "interpretation_relevant_evidence_gain": "",
            "reviewer_burden": "",
            "N": augmented_cases,
        },
    )


def _traceability_row_from_report(payload: Mapping[str, Any]) -> Mapping[str, object]:
    traceability = _mapping(_mapping(payload.get("overall")).get("traceability"))
    return {
        "strategy_or_baseline_id": str(payload.get("strategy_or_baseline_id") or ""),
        "citation_validity_rate": _optional_float(traceability.get("citation_validity_rate")),
        "hallucinated_citation_rate": _optional_float(traceability.get("hallucinated_citation_rate")),
        "span_boundary_f1": _optional_float(traceability.get("span_boundary_f1")),
        "evidence_support_rate": _optional_float(traceability.get("evidence_support_rate")),
        "traceable_f1": _float(traceability.get("traceable_f1")),
        "cross_lingual_consistency": _optional_float(traceability.get("cross_lingual_consistency")),
    }


def _load_optional_traceability_report(
    manifest: Mapping[str, Any],
    *,
    manifest_path: Path,
) -> Mapping[str, Any] | None:
    source_reports = _mapping(manifest.get("source_reports"))
    raw_traceability_path = source_reports.get("traceability_report")
    if not raw_traceability_path:
        return None
    traceability_path = _resolve_report_path(str(raw_traceability_path), manifest_path=manifest_path)
    if traceability_path is None:
        return None
    return _load_json_object(traceability_path)


def _load_optional_diagnosis_report(
    manifest: Mapping[str, Any],
    *,
    manifest_path: Path,
) -> Mapping[str, Any] | None:
    source_reports = _mapping(manifest.get("source_reports"))
    ablation_report = str(source_reports.get("ablation_report") or "")
    reports_dir = _reports_dir_from_manifest(source_reports, manifest_path=manifest_path)
    candidates = sorted(reports_dir.glob("contextual_reconcile_diagnosis_*.json"))
    if not candidates:
        return None

    latest_payload: Mapping[str, Any] | None = None
    for candidate in reversed(candidates):
        payload = _load_json_object(candidate)
        if _same_report_path(str(payload.get("report_path") or ""), ablation_report):
            return payload
        if latest_payload is None:
            latest_payload = payload
    return latest_payload


def _reports_dir_from_manifest(source_reports: Mapping[str, Any], *, manifest_path: Path) -> Path:
    for key in ("ablation_report", "g2_report", "traceability_report", "coverage_report"):
        raw_path = source_reports.get(key)
        if not raw_path:
            continue
        report_path = _resolve_report_path(str(raw_path), manifest_path=manifest_path)
        if report_path is not None:
            return report_path.parent
    return manifest_path.parent


def _strategy_by_name(manifest: Mapping[str, Any], strategy_name: str) -> Mapping[str, Any]:
    for strategy in _list(manifest.get("strategies")):
        if isinstance(strategy, Mapping) and strategy.get("strategy") == strategy_name:
            return cast(Mapping[str, Any], strategy)
    return {}


def _load_json_object(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"Expected JSON object in {path}")
    return cast(Mapping[str, Any], payload)


def _resolve_report_path(raw_path: str, *, manifest_path: Path) -> Path | None:
    candidates = (Path(raw_path), manifest_path.parent / raw_path)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _same_report_path(left: str, right: str) -> bool:
    if not left or not right:
        return False
    left_path = Path(left)
    right_path = Path(right)
    if left_path.exists() and right_path.exists():
        return left_path.resolve() == right_path.resolve()
    return left_path.as_posix() == right_path.as_posix()


def _format_markdown(tables: MainPaperTables) -> str:
    lines = [
        "# BIBM Main Paper Tables",
        "",
        f"Generated at: `{tables.generated_at}`",
        f"Manifest: `{tables.manifest_path}`",
        "",
    ]
    for table in tables.tables:
        lines.extend(_format_markdown_table(table))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _format_markdown_table(table: MainPaperTable) -> list[str]:
    lines = [f"## {table.title}"]
    if not table.rows:
        return lines + ["", "_No rows._"]
    columns = _columns(table.rows)
    lines.append("| " + " | ".join(columns) + " |")
    lines.append("| " + " | ".join("---" for _ in columns) + " |")
    for row in table.rows:
        lines.append("| " + " | ".join(_markdown_cell(row.get(column)) for column in columns) + " |")
    return lines


def _write_csv(tables: MainPaperTables, csv_path: Path) -> None:
    rows: list[Mapping[str, object]] = []
    for table in tables.tables:
        for row in table.rows:
            rows.append({"table": table.title, **row})
    columns = _columns(rows)
    with csv_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _columns(rows: list[Mapping[str, object]] | tuple[Mapping[str, object], ...]) -> list[str]:
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


def _readiness_status(value: object) -> str:
    if isinstance(value, str) and value:
        return "report-available"
    return "not-yet-reportable"


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


def _root_cause_rank(row: Mapping[str, object]) -> int:
    root_cause = str(row.get("root_cause") or "")
    if root_cause in ERROR_ROOT_CAUSE_ORDER:
        return ERROR_ROOT_CAUSE_ORDER.index(root_cause)
    return len(ERROR_ROOT_CAUSE_ORDER)


if __name__ == "__main__":
    main()
