"""Diagnose N=50 English-pivot tri-state false negatives from saved artifacts."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from benchmark.core.matching import compare_evidence


DEFAULT_BUCKETS = Path("benchmark/data/reports/n50/c2_english_pivot_tristate_fn_death_buckets_20260701.json")
DEFAULT_REPORT = Path("benchmark/data/reports/n50/c2_english_pivot_tristate_20260701_024458.json")
DEFAULT_OUTPUT = Path(
    "benchmark/data/reports/n50/c2_english_pivot_tristate_phase2_fn_diagnosis_20260701.json"
)
DEFAULT_PIPELINE_ROOT = Path("data/pipeline")

PRIMARY_BUCKET = "primary_or_candidate_generation_missing"
BOUNDARY_BUCKET = "scorer_or_gold_boundary_mismatch"
SOURCE_BUCKET = "source_grounding_or_quote_invalid"


def main() -> None:
    """Run the offline diagnosis."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--buckets", type=Path, default=DEFAULT_BUCKETS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--pipeline-root", type=Path, default=DEFAULT_PIPELINE_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    buckets = _load_json(args.buckets)
    report = _load_json(args.report)
    run_ids = {
        str(entry["entry_id"]): str(entry["run_id"])
        for entry in report.get("per_entry", [])
        if entry.get("entry_id") and entry.get("run_id")
    }

    rows = [row for row in buckets.get("rows", []) if isinstance(row, dict)]
    artifact_cache: dict[str, dict[str, Any] | None] = {}

    diagnosed_rows: list[dict[str, Any]] = []
    secondary_counts: Counter[str] = Counter()
    secondary_by_field: dict[str, Counter[str]] = defaultdict(Counter)
    phase2_label_counts: Counter[str] = Counter()
    phase2_labels_by_bucket: dict[str, Counter[str]] = defaultdict(Counter)
    phase2_examples_by_label: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for row in rows:
        phase2_label = _classify_phase2_vs_final(row, run_ids, artifact_cache, args.pipeline_root)
        phase2_label_counts[phase2_label] += 1
        phase2_labels_by_bucket[str(row.get("bucket", ""))][phase2_label] += 1
        if len(phase2_examples_by_label[phase2_label]) < 8:
            phase2_examples_by_label[phase2_label].append(
                _artifact_row_slice(row, run_ids, artifact_cache, args.pipeline_root)
            )

        if row.get("bucket") != PRIMARY_BUCKET:
            continue
        diagnosis = _diagnose_primary_bucket_row(row, run_ids, artifact_cache, args.pipeline_root)
        diagnosed_rows.append(diagnosis)
        secondary = str(diagnosis["secondary_bucket"])
        secondary_counts[secondary] += 1
        secondary_by_field[str(row.get("field_id", ""))][secondary] += 1

    variant_type_boundary = [
        _artifact_row_slice(row, run_ids, artifact_cache, args.pipeline_root)
        for row in rows
        if row.get("bucket") == BOUNDARY_BUCKET and row.get("field_id") == "A.variant_type"
    ]
    hgvs_p_source_invalid = [
        _artifact_row_slice(row, run_ids, artifact_cache, args.pipeline_root)
        for row in rows
        if row.get("bucket") == SOURCE_BUCKET and row.get("field_id") == "A.variant_hgvs_p"
    ]

    output = {
        "inputs": {
            "buckets": str(args.buckets),
            "report": str(args.report),
            "pipeline_root": str(args.pipeline_root),
        },
        "primary_bucket_total": len(diagnosed_rows),
        "primary_bucket_secondary_counts": secondary_counts.most_common(),
        "primary_bucket_secondary_by_field": {
            field_id: counter.most_common()
            for field_id, counter in sorted(secondary_by_field.items())
        },
        "primary_bucket_top_fields": Counter(str(row.get("field_id", "")) for row in diagnosed_rows).most_common(30),
        "primary_bucket_examples_by_secondary": _examples_by_secondary(diagnosed_rows),
        "all_fn_phase2_vs_final_counts": phase2_label_counts.most_common(),
        "all_fn_phase2_vs_final_by_original_bucket": {
            bucket: counter.most_common()
            for bucket, counter in sorted(phase2_labels_by_bucket.items())
        },
        "all_fn_phase2_vs_final_examples": dict(phase2_examples_by_label),
        "variant_type_boundary_mismatch": {
            "count": len(variant_type_boundary),
            "rows": variant_type_boundary,
            "value_pairs": Counter(
                (
                    str(row.get("expected", "")),
                    " | ".join(str(value) for value in row.get("reconciled_found_values", [])),
                )
                for row in variant_type_boundary
            ).most_common(),
        },
        "variant_hgvs_p_source_invalid": {
            "count": len(hgvs_p_source_invalid),
            "rows": hgvs_p_source_invalid,
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(f"Wrote {args.output}")


def _classify_phase2_vs_final(
    row: dict[str, Any],
    run_ids: dict[str, str],
    artifact_cache: dict[str, dict[str, Any] | None],
    pipeline_root: Path,
) -> str:
    entry_id = str(row.get("entry_id", ""))
    field_id = str(row.get("field_id", ""))
    expected = str(row.get("expected", ""))
    artifact = _load_artifact(entry_id, run_ids, artifact_cache, pipeline_root)
    if artifact is None:
        return "artifact_missing"

    translated_items = _field_items(artifact, "translated_result", field_id)
    reconciled_items = _field_items(artifact, "reconciled_result", field_id)
    translated_found = [item for item in translated_items if item.get("status") == "found"]
    reconciled_found = [item for item in reconciled_items if item.get("status") == "found"]
    translated_source_invalid = [item for item in translated_items if item.get("status") == "source_invalid"]
    reconciled_source_invalid = [item for item in reconciled_items if item.get("status") == "source_invalid"]

    if _matches_expected(field_id, expected, reconciled_items):
        return "phase2_reconciled_correct_but_final_missing"
    if _matches_expected(field_id, expected, translated_items):
        return "pre_reconcile_correct_but_reconcile_or_final_missing"
    if _matches_expected(field_id, expected, _promote_source_invalid(translated_items)):
        return "source_invalid_value_would_match_if_admitted"
    if translated_found or reconciled_found or translated_source_invalid or reconciled_source_invalid:
        return "phase2_candidate_present_but_wrong_or_invalid"
    return "phase2_no_found_candidate"


def _diagnose_primary_bucket_row(
    row: dict[str, Any],
    run_ids: dict[str, str],
    artifact_cache: dict[str, dict[str, Any] | None],
    pipeline_root: Path,
) -> dict[str, Any]:
    entry_id = str(row.get("entry_id", ""))
    field_id = str(row.get("field_id", ""))
    expected = str(row.get("expected", ""))
    artifact = _load_artifact(entry_id, run_ids, artifact_cache, pipeline_root)
    base = dict(row)

    if artifact is None:
        return {
            **base,
            "secondary_bucket": "artifact_missing",
            "translated_items": [],
            "reconciled_items": [],
        }

    translated_items = _field_items(artifact, "translated_result", field_id)
    reconciled_items = _field_items(artifact, "reconciled_result", field_id)
    translated_found = [item for item in translated_items if item.get("status") == "found"]
    reconciled_found = [item for item in reconciled_items if item.get("status") == "found"]

    translated_match = _matches_expected(field_id, expected, translated_items)
    reconciled_match = _matches_expected(field_id, expected, reconciled_items)
    if translated_match:
        secondary = "pre_reconcile_value_match_suppressed"
    elif translated_found:
        secondary = "pre_reconcile_wrong_value_or_boundary"
    elif translated_items:
        secondary = "pre_reconcile_not_found_only"
    else:
        secondary = "pre_reconcile_no_field_item"

    if reconciled_match:
        secondary = "report_or_scorer_mismatch_after_reconcile"
    elif reconciled_found and not translated_found:
        secondary = "reconcile_created_wrong_value"

    return {
        **base,
        "secondary_bucket": secondary,
        "translated_match": translated_match,
        "reconciled_match": reconciled_match,
        "translated_items": [_compact_item(item) for item in translated_items],
        "reconciled_items": [_compact_item(item) for item in reconciled_items],
        "translated_found_values": [_item_value_text(item) for item in translated_found],
        "reconciled_found_values": [_item_value_text(item) for item in reconciled_found],
    }


def _artifact_row_slice(
    row: dict[str, Any],
    run_ids: dict[str, str],
    artifact_cache: dict[str, dict[str, Any] | None],
    pipeline_root: Path,
) -> dict[str, Any]:
    entry_id = str(row.get("entry_id", ""))
    field_id = str(row.get("field_id", ""))
    artifact = _load_artifact(entry_id, run_ids, artifact_cache, pipeline_root)
    translated_items = _field_items(artifact, "translated_result", field_id) if artifact else []
    reconciled_items = _field_items(artifact, "reconciled_result", field_id) if artifact else []
    return {
        **row,
        "translated_items": [_compact_item(item) for item in translated_items],
        "reconciled_items": [_compact_item(item) for item in reconciled_items],
        "translated_found_values": [
            _item_value_text(item)
            for item in translated_items
            if item.get("status") == "found"
        ],
        "reconciled_found_values": [
            _item_value_text(item)
            for item in reconciled_items
            if item.get("status") == "found"
        ],
    }


def _load_artifact(
    entry_id: str,
    run_ids: dict[str, str],
    artifact_cache: dict[str, dict[str, Any] | None],
    pipeline_root: Path,
) -> dict[str, Any] | None:
    run_id = run_ids.get(entry_id)
    if not run_id:
        return None
    if run_id in artifact_cache:
        return artifact_cache[run_id]
    artifact_path = pipeline_root / run_id / "phase_2" / "extraction_result.json"
    if not artifact_path.exists():
        artifact_cache[run_id] = None
        return None
    artifact_cache[run_id] = _load_json(artifact_path)
    return artifact_cache[run_id]


def _field_items(artifact: dict[str, Any], result_key: str, field_id: str) -> list[dict[str, Any]]:
    result = artifact.get(result_key, {})
    if not isinstance(result, dict):
        return []
    raw_items = result.get("evidence_items", [])
    if not isinstance(raw_items, list):
        return []
    return [
        item
        for item in raw_items
        if isinstance(item, dict) and item.get("field_id") == field_id
    ]


def _matches_expected(field_id: str, expected: str, items: list[dict[str, Any]]) -> bool:
    if not items:
        return False
    matches = compare_evidence([{"field_id": field_id, "value": expected}], items)
    return bool(matches and matches[0].matched)


def _promote_source_invalid(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    promoted: list[dict[str, Any]] = []
    for item in items:
        if item.get("status") != "source_invalid":
            promoted.append(item)
            continue
        promoted_item = dict(item)
        promoted_item["status"] = "found"
        promoted.append(promoted_item)
    return promoted


def _compact_item(item: dict[str, Any]) -> dict[str, Any]:
    source = item.get("source") if isinstance(item.get("source"), dict) else None
    raw_source = item.get("raw_source") if isinstance(item.get("raw_source"), dict) else None
    return {
        "status": item.get("status"),
        "value": _item_value_text(item),
        "confidence": item.get("confidence"),
        "group_id": item.get("group_id"),
        "notes": item.get("notes"),
        "source_text": source.get("text_snippet") if source else None,
        "source_precision": source.get("source_precision") if source else None,
        "raw_source_text": raw_source.get("text_snippet") if raw_source else None,
        "raw_source_precision": raw_source.get("source_precision") if raw_source else None,
    }


def _examples_by_secondary(rows: list[dict[str, Any]], limit: int = 5) -> dict[str, list[dict[str, Any]]]:
    examples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        secondary = str(row.get("secondary_bucket", ""))
        if len(examples[secondary]) >= limit:
            continue
        examples[secondary].append(row)
    return dict(examples)


def _item_value_text(item: dict[str, Any]) -> str:
    value = item.get("value", "")
    if isinstance(value, dict):
        for key in ("value", "text", "display_name"):
            nested = value.get(key)
            if nested not in (None, ""):
                return str(nested)
        return ""
    return "" if value is None else str(value)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


if __name__ == "__main__":
    main()
