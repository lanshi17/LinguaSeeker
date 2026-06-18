"""Block-level recall diagnostics for missing reconcile fields."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import json
import re
from pathlib import Path
import time
from typing import Any, Mapping, TypedDict, cast

from benchmark.core import GROUND_TRUTH_DIR, REPORTS_DIR


RELATIONSHIP_CUE_RE = re.compile(
    r"\b(caus(?:e|es|ed|ing)|pathogenic|biallelic|loss[- ]of[- ]function|"
    r"deficien(?:cy|t)|associated|susceptib|risk|predicted|may contribute|"
    r"refuted|disputed|conflicting|not associated|no evidence)\b",
    re.IGNORECASE,
)
TABLE_CUE_RE = re.compile(r"(^|\n)\s*Table\b|(^|\n)\s*\|.+\|", re.IGNORECASE)
SPACE_RE = re.compile(r"\s+")


class BlockRecallRowPayload(TypedDict):
    """Serializable row for one missing field."""

    entry_id: str
    field_id: str
    expected: str
    gene_symbol: str
    disease_label: str
    classification: str
    moi: str
    source_contains_gene: bool
    source_contains_disease: bool
    source_contains_expected_value: bool
    source_contains_relationship_cue: bool
    likely_table_related: bool
    likely_generation_missing: bool


class BlockRecallSummaryPayload(TypedDict):
    """Serializable block recall summary."""

    total_missing_fields: int
    likely_generation_missing: int
    likely_table_related: int
    by_field: dict[str, int]
    by_classification: dict[str, int]
    by_moi: dict[str, int]


class BlockRecallDiagnosticsPayload(TypedDict):
    """Serializable block recall diagnostics."""

    report_path: str
    ground_truth_dir: str
    summary: BlockRecallSummaryPayload
    rows: list[BlockRecallRowPayload]


@dataclass(frozen=True)
class BlockRecallRow:
    """One missing field with source-level recall cues."""

    entry_id: str
    field_id: str
    expected: str
    gene_symbol: str
    disease_label: str
    classification: str
    moi: str
    source_contains_gene: bool
    source_contains_disease: bool
    source_contains_expected_value: bool
    source_contains_relationship_cue: bool
    likely_table_related: bool
    likely_generation_missing: bool


@dataclass(frozen=True)
class BlockRecallSummary:
    """Aggregate block recall diagnosis."""

    total_missing_fields: int
    likely_generation_missing: int
    likely_table_related: int
    by_field: Mapping[str, int]
    by_classification: Mapping[str, int]
    by_moi: Mapping[str, int]


@dataclass(frozen=True)
class BlockRecallDiagnostics:
    """Complete block recall diagnostics."""

    report_path: Path
    ground_truth_dir: Path
    rows: tuple[BlockRecallRow, ...]
    summary: BlockRecallSummary


def build_block_recall_diagnostics(
    report_path: Path,
    *,
    ground_truth_dir: Path = GROUND_TRUTH_DIR,
    strategy: str = "source_grounded_reconcile",
) -> BlockRecallDiagnostics:
    """Build source-level recall diagnostics for missing fields in a strategy report."""
    report = _load_json_object(report_path)
    rows: list[BlockRecallRow] = []
    for entry in _strategy_entries(report, strategy):
        rows.extend(_missing_rows_for_entry(entry, ground_truth_dir))
    row_tuple = tuple(rows)
    return BlockRecallDiagnostics(
        report_path=report_path,
        ground_truth_dir=ground_truth_dir,
        rows=row_tuple,
        summary=_summarize(row_tuple),
    )


def diagnostics_to_payload(
    diagnostics: BlockRecallDiagnostics,
) -> BlockRecallDiagnosticsPayload:
    """Convert block recall diagnostics to JSON payload."""
    return {
        "report_path": str(diagnostics.report_path),
        "ground_truth_dir": str(diagnostics.ground_truth_dir),
        "summary": {
            "total_missing_fields": diagnostics.summary.total_missing_fields,
            "likely_generation_missing": diagnostics.summary.likely_generation_missing,
            "likely_table_related": diagnostics.summary.likely_table_related,
            "by_field": dict(diagnostics.summary.by_field),
            "by_classification": dict(diagnostics.summary.by_classification),
            "by_moi": dict(diagnostics.summary.by_moi),
        },
        "rows": [
            {
                "entry_id": row.entry_id,
                "field_id": row.field_id,
                "expected": row.expected,
                "gene_symbol": row.gene_symbol,
                "disease_label": row.disease_label,
                "classification": row.classification,
                "moi": row.moi,
                "source_contains_gene": row.source_contains_gene,
                "source_contains_disease": row.source_contains_disease,
                "source_contains_expected_value": row.source_contains_expected_value,
                "source_contains_relationship_cue": row.source_contains_relationship_cue,
                "likely_table_related": row.likely_table_related,
                "likely_generation_missing": row.likely_generation_missing,
            }
            for row in diagnostics.rows
        ],
    }


def write_block_recall_diagnostics(
    diagnostics: BlockRecallDiagnostics,
    reports_dir: Path = REPORTS_DIR,
) -> Path:
    """Persist block recall diagnostics."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    output_path = reports_dir / f"block_recall_diagnosis_{time.strftime('%Y%m%d_%H%M%S')}.json"
    output_path.write_text(
        json.dumps(diagnostics_to_payload(diagnostics), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint for block recall diagnostics."""
    parser = argparse.ArgumentParser(description="Diagnose source-level cues for missing fields.")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--ground-truth-dir", type=Path, default=GROUND_TRUTH_DIR)
    parser.add_argument("--strategy", default="source_grounded_reconcile")
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    diagnostics = build_block_recall_diagnostics(
        args.report,
        ground_truth_dir=args.ground_truth_dir,
        strategy=args.strategy,
    )
    payload = diagnostics_to_payload(diagnostics)
    print(f"total_missing_fields={payload['summary']['total_missing_fields']}")
    print(f"likely_generation_missing={payload['summary']['likely_generation_missing']}")
    print(f"likely_table_related={payload['summary']['likely_table_related']}")
    if args.write:
        print(f"REPORT: {write_block_recall_diagnostics(diagnostics, args.reports_dir)}")


def _load_json_object(path: Path) -> Mapping[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return cast(Mapping[str, Any], payload)


def _strategy_entries(report: Mapping[str, Any], strategy: str) -> tuple[Mapping[str, Any], ...]:
    for raw_strategy in report.get("strategies", []):
        if not isinstance(raw_strategy, dict):
            continue
        if raw_strategy.get("strategy") != strategy:
            continue
        per_entry = raw_strategy.get("per_entry", [])
        if not isinstance(per_entry, list):
            return ()
        return tuple(cast(Mapping[str, Any], entry) for entry in per_entry if isinstance(entry, dict))
    raise ValueError(f"Strategy not found: {strategy}")


def _missing_rows_for_entry(
    entry: Mapping[str, Any],
    ground_truth_dir: Path,
) -> list[BlockRecallRow]:
    entry_id = str(entry.get("entry_id", ""))
    expected_payload = _load_expected(ground_truth_dir / entry_id / "expected.json")
    source_text = _read_text(ground_truth_dir / entry_id / "source.md")
    normalized_source = _normalize(source_text)
    gene_symbol = str(expected_payload.get("gene_symbol") or entry.get("gene_symbol", ""))
    disease_label = str(expected_payload.get("disease_label", ""))
    classification = str(expected_payload.get("classification") or entry.get("classification", ""))
    moi = str(expected_payload.get("moi") or entry.get("moi", ""))
    rows: list[BlockRecallRow] = []
    for field_match in entry.get("field_matches", []):
        if not isinstance(field_match, dict):
            continue
        if str(field_match.get("match_type", "")) not in {"missing", "none"}:
            continue
        field_id = str(field_match.get("field_id", ""))
        expected = str(field_match.get("expected", ""))
        source_contains_gene = _contains(normalized_source, gene_symbol)
        source_contains_disease = _contains(normalized_source, disease_label)
        source_contains_expected_value = _contains(normalized_source, expected)
        source_contains_relationship_cue = bool(RELATIONSHIP_CUE_RE.search(source_text))
        likely_table_related = _likely_table_related(source_text, gene_symbol, disease_label, expected)
        likely_generation_missing = (
            source_contains_expected_value
            or (source_contains_gene and source_contains_disease)
            or (field_id == "A.gene_disease_relationship" and source_contains_gene and source_contains_relationship_cue)
        )
        rows.append(
            BlockRecallRow(
                entry_id=entry_id,
                field_id=field_id,
                expected=expected,
                gene_symbol=gene_symbol,
                disease_label=disease_label,
                classification=classification,
                moi=moi,
                source_contains_gene=source_contains_gene,
                source_contains_disease=source_contains_disease,
                source_contains_expected_value=source_contains_expected_value,
                source_contains_relationship_cue=source_contains_relationship_cue,
                likely_table_related=likely_table_related,
                likely_generation_missing=likely_generation_missing,
            )
        )
    return rows


def _load_expected(path: Path) -> Mapping[str, Any]:
    if not path.exists():
        return {}
    return _load_json_object(path)


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _contains(normalized_source: str, needle: str) -> bool:
    normalized_needle = _normalize(needle)
    return bool(normalized_needle) and normalized_needle in normalized_source


def _normalize(value: str) -> str:
    return SPACE_RE.sub(" ", value.casefold()).strip()


def _likely_table_related(
    source_text: str,
    gene_symbol: str,
    disease_label: str,
    expected: str,
) -> bool:
    if not TABLE_CUE_RE.search(source_text):
        return False
    normalized_source = _normalize(source_text)
    return any(
        _contains(normalized_source, value)
        for value in (gene_symbol, disease_label, expected)
    )


def _summarize(rows: tuple[BlockRecallRow, ...]) -> BlockRecallSummary:
    return BlockRecallSummary(
        total_missing_fields=len(rows),
        likely_generation_missing=sum(1 for row in rows if row.likely_generation_missing),
        likely_table_related=sum(1 for row in rows if row.likely_table_related),
        by_field=_counter(row.field_id for row in rows),
        by_classification=_counter(row.classification for row in rows),
        by_moi=_counter(row.moi for row in rows),
    )


def _counter(values: object) -> dict[str, int]:
    return dict(Counter(cast(Any, values)))


if __name__ == "__main__":
    main()
