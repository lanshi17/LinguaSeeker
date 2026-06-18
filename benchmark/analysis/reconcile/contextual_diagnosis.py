"""Diagnose why contextual reconcile does not improve a same-report baseline."""
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

ROOT_CAUSE_ORDER = (
    "candidate_absent",
    "source_invalid_or_unscorable",
    "source_label_visibility_limit",
    "wrong_relationship_semantics",
    "disease_boundary_error",
    "non_target_contamination",
    "score_ranking_error",
    "threshold_or_margin_error",
    "table_or_caption_recall_error",
    "evaluation_normalization_gap",
)


class ContextualFieldDiagnosisPayload(TypedDict):
    """Serializable field-level contextual reconcile diagnosis."""

    entry_id: str
    field_id: str
    expected: str | None
    extracted: str | None
    matched: bool
    match_type: str
    root_cause: str
    candidate_count: int
    found_candidate_count: int
    source_valid_candidate_count: int
    source_precision: str | None
    best_score: float | None
    verifier_support_score: float | None
    target_specificity_score: float | None
    contradiction_penalty: float | None
    notes: list[str]


class ContextualDiagnosisSummaryPayload(TypedDict):
    """Serializable contextual diagnosis summary."""

    by_root_cause: dict[str, int]
    by_field: dict[str, int]
    by_match_type: dict[str, int]


class ContextualDiagnosisReportPayload(TypedDict):
    """Serializable contextual diagnosis report."""

    report_path: str
    strategy: str
    total_rows: int
    summary: ContextualDiagnosisSummaryPayload
    rows: list[ContextualFieldDiagnosisPayload]


@dataclass(frozen=True)
class ContextualFieldDiagnosis:
    """One field-level diagnosis row for contextual reconcile."""

    entry_id: str
    field_id: str
    expected: str | None
    extracted: str | None
    matched: bool
    match_type: str
    root_cause: str
    candidate_count: int
    found_candidate_count: int
    source_valid_candidate_count: int
    source_precision: str | None
    best_score: float | None
    verifier_support_score: float | None
    target_specificity_score: float | None
    contradiction_penalty: float | None
    notes: tuple[str, ...]


@dataclass(frozen=True)
class ContextualDiagnosisSummary:
    """Aggregate diagnosis counts."""

    by_root_cause: Mapping[str, int]
    by_field: Mapping[str, int]
    by_match_type: Mapping[str, int]


@dataclass(frozen=True)
class ContextualDiagnosisReport:
    """Contextual reconcile diagnosis report."""

    report_path: Path
    strategy: str
    rows: tuple[ContextualFieldDiagnosis, ...]
    summary: ContextualDiagnosisSummary


def build_contextual_reconcile_diagnosis(
    report_path: Path,
    *,
    strategy: str = "context_verifier_reconcile",
) -> ContextualDiagnosisReport:
    """Build a field-level no-lift diagnosis from a reconcile ablation report."""
    payload = _load_report(report_path)
    rows = tuple(_iter_strategy_rows(payload, strategy))
    return ContextualDiagnosisReport(
        report_path=report_path,
        strategy=strategy,
        rows=rows,
        summary=_summarize(rows),
    )


def contextual_diagnosis_to_payload(
    diagnosis: ContextualDiagnosisReport,
) -> ContextualDiagnosisReportPayload:
    """Convert contextual diagnosis to a JSON-serializable payload."""
    return {
        "report_path": str(diagnosis.report_path),
        "strategy": diagnosis.strategy,
        "total_rows": len(diagnosis.rows),
        "summary": {
            "by_root_cause": dict(diagnosis.summary.by_root_cause),
            "by_field": dict(diagnosis.summary.by_field),
            "by_match_type": dict(diagnosis.summary.by_match_type),
        },
        "rows": [
            {
                "entry_id": row.entry_id,
                "field_id": row.field_id,
                "expected": row.expected,
                "extracted": row.extracted,
                "matched": row.matched,
                "match_type": row.match_type,
                "root_cause": row.root_cause,
                "candidate_count": row.candidate_count,
                "found_candidate_count": row.found_candidate_count,
                "source_valid_candidate_count": row.source_valid_candidate_count,
                "source_precision": row.source_precision,
                "best_score": row.best_score,
                "verifier_support_score": row.verifier_support_score,
                "target_specificity_score": row.target_specificity_score,
                "contradiction_penalty": row.contradiction_penalty,
                "notes": list(row.notes),
            }
            for row in diagnosis.rows
        ],
    }


def write_contextual_reconcile_diagnosis(
    diagnosis: ContextualDiagnosisReport,
    reports_dir: Path = REPORTS_DIR,
) -> Path:
    """Persist contextual reconcile diagnosis to the reports directory."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    output_path = reports_dir / f"contextual_reconcile_diagnosis_{time.strftime('%Y%m%d_%H%M%S')}.json"
    output_path.write_text(
        json.dumps(contextual_diagnosis_to_payload(diagnosis), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint for contextual reconcile diagnostics."""
    parser = argparse.ArgumentParser(description="Diagnose contextual reconcile no-lift failures.")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--strategy", default="context_verifier_reconcile")
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    diagnosis = build_contextual_reconcile_diagnosis(args.report, strategy=args.strategy)
    payload = contextual_diagnosis_to_payload(diagnosis)
    print(f"rows={payload['total_rows']}")
    print(f"by_root_cause={payload['summary']['by_root_cause']}")
    if args.write:
        print(f"REPORT: {write_contextual_reconcile_diagnosis(diagnosis, args.reports_dir)}")


def _load_report(report_path: Path) -> Mapping[str, Any]:
    if not report_path.exists():
        raise FileNotFoundError(report_path)
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {report_path}")
    return cast(Mapping[str, Any], payload)


def _iter_strategy_rows(
    payload: Mapping[str, Any],
    strategy: str,
) -> tuple[ContextualFieldDiagnosis, ...]:
    rows: list[ContextualFieldDiagnosis] = []
    for raw_strategy in payload.get("strategies", []):
        if not isinstance(raw_strategy, dict) or raw_strategy.get("strategy") != strategy:
            continue
        per_entry = raw_strategy.get("per_entry", [])
        if not isinstance(per_entry, list):
            continue
        for raw_entry in per_entry:
            if isinstance(raw_entry, dict):
                rows.extend(_entry_rows(raw_entry))
    return tuple(rows)


def _entry_rows(raw_entry: Mapping[str, Any]) -> list[ContextualFieldDiagnosis]:
    field_matches = raw_entry.get("field_matches", [])
    if not isinstance(field_matches, list):
        return []
    rows: list[ContextualFieldDiagnosis] = []
    for raw_match in field_matches:
        if not isinstance(raw_match, dict):
            continue
        if _should_include_match(raw_match):
            rows.append(_build_row(str(raw_entry.get("entry_id", "")), raw_match))
    return rows


def _should_include_match(raw_match: Mapping[str, Any]) -> bool:
    """Return True only for rows that still need diagnosis."""
    if not bool(raw_match.get("matched", False)):
        return True
    return _extra_found_count(raw_match) > 0


def _build_row(entry_id: str, raw_match: Mapping[str, Any]) -> ContextualFieldDiagnosis:
    source_span = raw_match.get("source_span")
    source_precision = _source_precision(source_span)
    extracted = raw_match.get("extracted")
    candidate_count = _candidate_count(raw_match)
    source_valid_count = 1 if isinstance(source_span, dict) else 0
    notes = _notes(raw_match, candidate_count, source_valid_count)
    return ContextualFieldDiagnosis(
        entry_id=entry_id,
        field_id=str(raw_match.get("field_id", "")),
        expected=_optional_str(raw_match.get("expected")),
        extracted=_optional_str(extracted),
        matched=bool(raw_match.get("matched", False)),
        match_type=str(raw_match.get("match_type", "")),
        root_cause=_root_cause(raw_match, candidate_count, source_valid_count),
        candidate_count=candidate_count,
        found_candidate_count=candidate_count,
        source_valid_candidate_count=source_valid_count,
        source_precision=source_precision,
        best_score=_optional_float(raw_match.get("best_score")),
        verifier_support_score=_optional_float(raw_match.get("verifier_support_score")),
        target_specificity_score=_optional_float(raw_match.get("target_specificity_score")),
        contradiction_penalty=_optional_float(raw_match.get("contradiction_penalty")),
        notes=notes,
    )


def _root_cause(
    raw_match: Mapping[str, Any],
    candidate_count: int,
    source_valid_count: int,
) -> str:
    field_id = str(raw_match.get("field_id", ""))
    matched = bool(raw_match.get("matched", False))
    extra_found_count = _extra_found_count(raw_match)
    if candidate_count == 0:
        return "candidate_absent"
    if source_valid_count == 0:
        return "source_invalid_or_unscorable"
    if field_id == RELATIONSHIP_FIELD_ID and not matched and _is_source_label_visibility_limit(raw_match):
        return "source_label_visibility_limit"
    if field_id == RELATIONSHIP_FIELD_ID and not matched:
        return "wrong_relationship_semantics"
    if field_id in DISEASE_FIELD_IDS and (not matched or extra_found_count > 0):
        return "disease_boundary_error"
    if extra_found_count > 0:
        return "non_target_contamination"
    if not matched:
        return "score_ranking_error"
    return "evaluation_normalization_gap"


def _candidate_count(raw_match: Mapping[str, Any]) -> int:
    match_type = str(raw_match.get("match_type", ""))
    base_count = 0 if match_type == "missing" and raw_match.get("extracted") is None else 1
    return base_count + _extra_found_count(raw_match)


def _extra_found_count(raw_match: Mapping[str, Any]) -> int:
    extra_found_values = raw_match.get("extra_found_values", [])
    return len(extra_found_values) if isinstance(extra_found_values, list) else 0


def _notes(
    raw_match: Mapping[str, Any],
    candidate_count: int,
    source_valid_count: int,
) -> tuple[str, ...]:
    notes: list[str] = []
    if candidate_count == 0:
        notes.append("No found candidate is visible in this ablation report for the field.")
    if candidate_count > 0 and source_valid_count == 0:
        notes.append("Candidate is present but this report does not show a valid source span.")
    if _extra_found_count(raw_match) > 0:
        notes.append("Matched field includes extra found values that contribute false positives.")
    if not any(key in raw_match for key in ("best_score", "verifier_support_score", "target_specificity_score")):
        notes.append("Score components are unavailable in the current ablation report.")
    return tuple(notes)


def _source_precision(source_span: object) -> str | None:
    if not isinstance(source_span, dict):
        return None
    precision = source_span.get("source_precision")
    return None if precision is None else str(precision)


def _is_source_label_visibility_limit(raw_match: Mapping[str, Any]) -> bool:
    expected = str(raw_match.get("expected") or "").casefold()
    extracted = str(raw_match.get("extracted") or "").casefold()
    source_span = raw_match.get("source_span")
    if not expected or expected == extracted or not isinstance(source_span, Mapping):
        return False
    snippet = str(source_span.get("text_snippet") or "").casefold()
    if not snippet:
        return False
    if expected == "refuted":
        return not any(term in snippet for term in ("no evidence", "not associated", "refuted", "refute"))
    if expected == "causative":
        causal_terms = ("cause", "causal", "causative", "disease-causing", "pathogenic variant", "biallelic")
        weak_terms = ("unclear", "incidental finding", "associated", "moderate:")
        return any(term in snippet for term in weak_terms) and not any(term in snippet for term in causal_terms)
    if expected == "disputed":
        return not any(term in snippet for term in ("disputed", "conflict", "conflicting", "controversial"))
    return False


def _optional_str(value: object) -> str | None:
    return None if value is None else str(value)


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _summarize(rows: tuple[ContextualFieldDiagnosis, ...]) -> ContextualDiagnosisSummary:
    return ContextualDiagnosisSummary(
        by_root_cause=_ordered_counter(row.root_cause for row in rows),
        by_field=dict(Counter(row.field_id for row in rows)),
        by_match_type=dict(Counter(row.match_type for row in rows)),
    )


def _ordered_counter(values: object) -> dict[str, int]:
    counter = Counter(cast(Any, values))
    ordered: dict[str, int] = {}
    for key in ROOT_CAUSE_ORDER:
        if counter[key]:
            ordered[key] = counter[key]
    for key, count in sorted(counter.items()):
        if key not in ordered:
            ordered[key] = count
    return ordered


if __name__ == "__main__":
    main()
