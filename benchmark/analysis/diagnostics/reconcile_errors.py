"""Diagnose reconcile strategy errors for main paper rescue."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import Any, Mapping, TypedDict, cast

from benchmark.core import REPORTS_DIR


RELATIONSHIP_FIELD_ID = "A.gene_disease_relationship"
DISEASE_FIELD_IDS = frozenset({"B.disease_diagnosis", "B.disease_phenotype"})
GENE_FIELD_IDS = frozenset({"A.gene_symbol"})


class FieldErrorRowPayload(TypedDict):
    """Serializable field-level error row."""

    entry_id: str
    strategy: str
    field_id: str
    expected: str
    extracted: str | None
    match_type: str
    source_precision: str | None
    has_source_span: bool
    extra_found_count: int
    classification: str
    moi: str
    error_types: list[str]


class ErrorSummaryPayload(TypedDict):
    """Serializable error summaries by axis."""

    by_strategy: dict[str, int]
    by_field: dict[str, int]
    by_classification: dict[str, int]
    by_moi: dict[str, int]
    by_source_precision: dict[str, int]
    by_error_type: dict[str, int]


class ReconcileErrorDiagnosticsPayload(TypedDict):
    """Serializable reconcile error diagnostics report."""

    report_path: str
    total_rows: int
    summary: ErrorSummaryPayload
    rows: list[FieldErrorRowPayload]


@dataclass(frozen=True)
class FieldErrorRow:
    """One field-level reconcile error row."""

    entry_id: str
    strategy: str
    field_id: str
    expected: str
    extracted: str | None
    match_type: str
    source_precision: str | None
    has_source_span: bool
    extra_found_count: int
    classification: str
    moi: str
    error_types: tuple[str, ...]


@dataclass(frozen=True)
class ErrorSummary:
    """Reconcile error summaries by common analysis axes."""

    by_strategy: Mapping[str, int]
    by_field: Mapping[str, int]
    by_classification: Mapping[str, int]
    by_moi: Mapping[str, int]
    by_source_precision: Mapping[str, int]
    by_error_type: Mapping[str, int]


@dataclass(frozen=True)
class ReconcileErrorDiagnostics:
    """Complete reconcile error diagnostics."""

    report_path: Path
    rows: tuple[FieldErrorRow, ...]
    summary: ErrorSummary


def build_reconcile_error_diagnostics(report_path: Path) -> ReconcileErrorDiagnostics:
    """Build error diagnostics from a reconcile ablation report."""
    payload = _load_report(report_path)
    rows = tuple(_iter_error_rows(payload))
    return ReconcileErrorDiagnostics(
        report_path=report_path,
        rows=rows,
        summary=_summarize(rows),
    )


def diagnostics_to_payload(
    diagnostics: ReconcileErrorDiagnostics,
) -> ReconcileErrorDiagnosticsPayload:
    """Convert diagnostics to a JSON-serializable payload."""
    return {
        "report_path": str(diagnostics.report_path),
        "total_rows": len(diagnostics.rows),
        "summary": {
            "by_strategy": dict(diagnostics.summary.by_strategy),
            "by_field": dict(diagnostics.summary.by_field),
            "by_classification": dict(diagnostics.summary.by_classification),
            "by_moi": dict(diagnostics.summary.by_moi),
            "by_source_precision": dict(diagnostics.summary.by_source_precision),
            "by_error_type": dict(diagnostics.summary.by_error_type),
        },
        "rows": [
            {
                "entry_id": row.entry_id,
                "strategy": row.strategy,
                "field_id": row.field_id,
                "expected": row.expected,
                "extracted": row.extracted,
                "match_type": row.match_type,
                "source_precision": row.source_precision,
                "has_source_span": row.has_source_span,
                "extra_found_count": row.extra_found_count,
                "classification": row.classification,
                "moi": row.moi,
                "error_types": list(row.error_types),
            }
            for row in diagnostics.rows
        ],
    }


def write_reconcile_error_diagnostics(
    diagnostics: ReconcileErrorDiagnostics,
    reports_dir: Path = REPORTS_DIR,
) -> Path:
    """Persist reconcile error diagnostics."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    output_path = reports_dir / f"reconcile_error_diagnosis_{time.strftime('%Y%m%d_%H%M%S')}.json"
    output_path.write_text(
        json.dumps(diagnostics_to_payload(diagnostics), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint for reconcile error diagnostics."""
    parser = argparse.ArgumentParser(description="Diagnose errors in reconcile ablation reports.")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    diagnostics = build_reconcile_error_diagnostics(args.report)
    payload = diagnostics_to_payload(diagnostics)
    print(f"rows={payload['total_rows']}")
    print(f"by_error_type={payload['summary']['by_error_type']}")
    if args.write:
        print(f"REPORT: {write_reconcile_error_diagnostics(diagnostics, args.reports_dir)}")


def _load_report(report_path: Path) -> Mapping[str, Any]:
    if not report_path.exists():
        raise FileNotFoundError(report_path)
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {report_path}")
    return cast(Mapping[str, Any], payload)


def _iter_error_rows(payload: Mapping[str, Any]) -> tuple[FieldErrorRow, ...]:
    rows: list[FieldErrorRow] = []
    for raw_strategy in payload.get("strategies", []):
        if not isinstance(raw_strategy, dict):
            continue
        strategy = str(raw_strategy.get("strategy", ""))
        per_entry = raw_strategy.get("per_entry", [])
        if not isinstance(per_entry, list):
            continue
        for raw_entry in per_entry:
            if not isinstance(raw_entry, dict):
                continue
            rows.extend(_entry_error_rows(strategy, raw_entry))
    return tuple(rows)


def _entry_error_rows(strategy: str, raw_entry: Mapping[str, Any]) -> list[FieldErrorRow]:
    rows: list[FieldErrorRow] = []
    field_matches = raw_entry.get("field_matches", [])
    if not isinstance(field_matches, list):
        return rows
    for raw_match in field_matches:
        if not isinstance(raw_match, dict):
            continue
        error_types = _classify_error_types(raw_match)
        if not error_types:
            continue
        source_span = raw_match.get("source_span")
        source_precision = _source_precision(source_span)
        extracted = raw_match.get("extracted")
        rows.append(
            FieldErrorRow(
                entry_id=str(raw_entry.get("entry_id", "")),
                strategy=strategy,
                field_id=str(raw_match.get("field_id", "")),
                expected=str(raw_match.get("expected", "")),
                extracted=None if extracted is None else str(extracted),
                match_type=str(raw_match.get("match_type", "")),
                source_precision=source_precision,
                has_source_span=isinstance(source_span, dict),
                extra_found_count=_extra_found_count(raw_match),
                classification=str(raw_entry.get("classification", "")),
                moi=str(raw_entry.get("moi", "")),
                error_types=error_types,
            )
        )
    return rows


def _classify_error_types(raw_match: Mapping[str, Any]) -> tuple[str, ...]:
    field_id = str(raw_match.get("field_id", ""))
    match_type = str(raw_match.get("match_type", ""))
    has_source_span = isinstance(raw_match.get("source_span"), dict)
    extra_found_count = _extra_found_count(raw_match)
    error_types: list[str] = []
    if match_type == "missing":
        error_types.append("missing")
        if not has_source_span:
            error_types.append("missing_without_any_candidate")
    elif match_type == "wrong_value":
        error_types.append("wrong_value")
        if has_source_span:
            error_types.append("wrong_value_with_valid_span")
    if extra_found_count > 0:
        error_types.append("over_extraction")
    if field_id == RELATIONSHIP_FIELD_ID and any(
        error_type in {"wrong_value", "missing"} for error_type in error_types
    ):
        error_types.append("relationship_semantics_error")
    if field_id in DISEASE_FIELD_IDS and any(
        error_type in {"wrong_value", "missing", "over_extraction"} for error_type in error_types
    ):
        error_types.append("disease_boundary_error")
    if field_id in GENE_FIELD_IDS and any(
        error_type in {"wrong_value", "missing", "over_extraction"} for error_type in error_types
    ):
        error_types.append("gene_symbol_error")
    return tuple(error_types)


def _extra_found_count(raw_match: Mapping[str, Any]) -> int:
    extra_values = raw_match.get("extra_found_values", [])
    return len(extra_values) if isinstance(extra_values, list) else 0


def _source_precision(source_span: object) -> str | None:
    if not isinstance(source_span, dict):
        return None
    value = source_span.get("source_precision")
    return None if value is None else str(value)


def _summarize(rows: tuple[FieldErrorRow, ...]) -> ErrorSummary:
    return ErrorSummary(
        by_strategy=_counter(row.strategy for row in rows),
        by_field=_counter(row.field_id for row in rows),
        by_classification=_counter(row.classification for row in rows),
        by_moi=_counter(row.moi for row in rows),
        by_source_precision=_counter(row.source_precision or "none" for row in rows),
        by_error_type=_counter(error_type for row in rows for error_type in row.error_types),
    )


def _counter(values: object) -> dict[str, int]:
    return dict(Counter(cast(Any, values)))


if __name__ == "__main__":
    main()
