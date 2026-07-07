"""Merge baseline retry reports into a primary baseline report."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from typing import Any, Mapping, cast

from benchmark.core.aggregate import compute_aggregate_metrics
from benchmark.core.contracts import EntryMetrics, FieldMatch


def merge_baseline_reports(
    *,
    primary_report_path: Path,
    retry_report_paths: tuple[Path, ...],
    reports_dir: Path,
) -> Path:
    """Write a primary report with retry entries replacing matching failures."""
    primary_report = dict(_load_json_object(primary_report_path))
    entries_by_id = {
        str(entry.get("entry_id") or ""): dict(entry)
        for entry in _entry_mappings(primary_report)
    }
    replaced_entry_ids: list[str] = []
    retry_source_paths: list[str] = []

    for retry_report_path in retry_report_paths:
        retry_report = _load_json_object(retry_report_path)
        retry_source_paths.append(str(retry_report_path))
        for retry_entry in _entry_mappings(retry_report):
            entry_id = str(retry_entry.get("entry_id") or "")
            if not entry_id or entry_id not in entries_by_id:
                continue
            if str(retry_entry.get("pipeline_status") or "") == "error":
                continue
            entries_by_id[entry_id] = dict(retry_entry)
            replaced_entry_ids.append(entry_id)

    ordered_entries = [
        entries_by_id[str(entry.get("entry_id") or "")]
        for entry in _entry_mappings(primary_report)
    ]
    primary_report["per_entry"] = ordered_entries
    primary_report["total_entries"] = len(ordered_entries)
    primary_report["aggregates"] = compute_aggregate_metrics(
        [_entry_metrics_from_payload(entry) for entry in ordered_entries]
    )
    primary_report["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    primary_report["evaluation_id"] = f"{primary_report.get('evaluation_id', 'baseline')}_merged_{time.strftime('%Y%m%d_%H%M%S')}"
    primary_report["config"] = {
        **dict(_mapping(primary_report.get("config"))),
        "primary_report": str(primary_report_path),
        "retry_reports": retry_source_paths,
        "retry_replaced_entries": sorted(set(replaced_entry_ids)),
    }

    reports_dir.mkdir(parents=True, exist_ok=True)
    output_path = reports_dir / f"{primary_report['evaluation_id']}.json"
    output_path.write_text(json.dumps(primary_report, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint for merging baseline retry reports."""
    parser = argparse.ArgumentParser(description="Merge baseline retry reports into a primary report.")
    parser.add_argument("--primary-report", type=Path, required=True)
    parser.add_argument("--retry-reports", nargs="+", type=Path, required=True)
    parser.add_argument("--reports-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    output_path = merge_baseline_reports(
        primary_report_path=args.primary_report,
        retry_report_paths=tuple(args.retry_reports),
        reports_dir=args.reports_dir,
    )
    print(f"REPORT: {output_path}")


def _entry_metrics_from_payload(entry: Mapping[str, Any]) -> EntryMetrics:
    return EntryMetrics(
        entry_id=str(entry.get("entry_id") or ""),
        gene_symbol=str(entry.get("gene_symbol") or ""),
        classification=str(entry.get("classification") or ""),
        language=str(entry.get("language") or ""),
        moi=str(entry.get("moi") or ""),
        pipeline_status=str(entry.get("pipeline_status") or ""),
        error_message=str(entry.get("error_message") or "") or None,
        duration_s=_float(entry.get("duration_s")),
        field_matches=[
            _field_match_from_payload(field_match)
            for field_match in _list(entry.get("field_matches"))
            if isinstance(field_match, Mapping)
        ],
        evidence_count=_int(entry.get("evidence_count")),
        found_rate=_float(entry.get("found_rate")),
    )


def _field_match_from_payload(field_match: Mapping[str, Any]) -> FieldMatch:
    return FieldMatch(
        field_id=str(field_match.get("field_id") or ""),
        expected_value=str(field_match.get("expected") or ""),
        matched=bool(field_match.get("matched")),
        extracted_value=_optional_string(field_match.get("extracted")),
        source_span=_optional_mapping(field_match.get("source_span")),
        match_type=str(field_match.get("match_type") or "none"),
        extra_found_values=[
            str(value)
            for value in _list(field_match.get("extra_found_values"))
        ],
    )


def _load_json_object(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"Expected JSON object in {path}")
    return cast(Mapping[str, Any], payload)


def _entry_mappings(report: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [
        cast(Mapping[str, Any], entry)
        for entry in _list(report.get("per_entry"))
        if isinstance(entry, Mapping)
    ]


def _mapping(value: object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return cast(Mapping[str, Any], value)
    return {}


def _optional_mapping(value: object) -> dict[str, object] | None:
    if isinstance(value, Mapping):
        return dict(value)
    return None


def _list(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    return []


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _int(value: object) -> int:
    if value is None or value == "":
        return 0
    return int(value)


def _float(value: object) -> float:
    if value is None or value == "":
        return 0.0
    return float(value)


if __name__ == "__main__":
    main()
