"""Build layer-3 reports from reusable PostgreSQL pipeline runs."""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import Any, Mapping, Sequence, TypedDict, cast
import uuid

from sqlalchemy import select

from benchmark.analysis.dataset_curation.inventory_system_runs import (
    SystemRunRow,
    build_inventory,
    load_expected_entry_ids,
    load_postgres_env_from_vault,
    query_system_run_rows,
)
from benchmark.core import (
    GROUND_TRUTH_DIR,
    REPORTS_DIR,
    EntryMetrics,
    FieldMatch,
    compare_entity_standardization,
    compare_evidence,
    compare_track_consistency,
    compute_aggregate_metrics,
)
from benchmark.core.evidence_metrics import query_evidence_metrics
from src.dao.postgresql.connection import async_session_factory, build_async_engine
from src.dao.postgresql.models import RunEvidenceItem


class ReportPayload(TypedDict):
    """Persisted evaluator-compatible report payload."""

    evaluation_id: str
    timestamp: str
    config: Mapping[str, object]
    total_entries: int
    total_duration_s: float
    aggregates: Mapping[str, object]
    per_entry: list[Mapping[str, object]]


@dataclass(frozen=True)
class ExtractedRunItem:
    """Field-level evidence loaded from ``run_evidence_items``."""

    field_id: str
    status: str
    value: object
    confidence: float
    source_span: dict[str, object]


def build_entry_metrics_from_run(
    entry: Mapping[str, Any],
    run_row: SystemRunRow,
    extracted_items: Sequence[ExtractedRunItem],
    found_rate: float,
    grounding_rate: float,
    entity_matches: Mapping[str, Mapping[str, object]],
    track_consistency: float,
    mondo: Any | None = None,
) -> EntryMetrics:
    """Build evaluator metrics for one entry from persisted DB evidence."""
    metrics = EntryMetrics(
        entry_id=str(entry["entry_id"]),
        gene_symbol=str(entry.get("gene_symbol", "")),
        classification=str(entry.get("classification", "")),
        language="en",
        moi=str(entry.get("moi", "")),
        run_id=run_row.processing_run_id,
        pipeline_status=run_row.pipeline_status,
        evidence_count=run_row.evidence_count,
        found_rate=found_rate,
        grounding_rate=grounding_rate,
        track_consistency=track_consistency,
    )
    comparable_items = [
        {
            "field_id": item.field_id,
            "status": item.status,
            "value": item.value,
            "confidence": item.confidence,
            "source_span": item.source_span,
        }
        for item in extracted_items
    ]
    metrics.field_matches = compare_evidence(
        list(entry.get("expected_evidence", [])),
        comparable_items,
        mondo=mondo,
        expected_standardization=cast(dict[str, str] | None, entry.get("expected_standardization")),
    )
    metrics.entity_matches = {
        entity_type: dict(match)
        for entity_type, match in entity_matches.items()
    }
    entity_total = len(metrics.entity_matches)
    entity_matched = sum(1 for match in metrics.entity_matches.values() if match.get("matched"))
    metrics.standardization_accuracy = entity_matched / entity_total if entity_total else 0.0
    return metrics


def build_report_payload(
    metrics_list: Sequence[EntryMetrics],
    inventory_total_expected: int,
) -> ReportPayload:
    """Build evaluator-compatible report JSON from entry metrics."""
    aggregates = compute_aggregate_metrics(list(metrics_list))
    return {
        "evaluation_id": f"eval_db_inventory_{uuid.uuid4().hex[:8]}",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "config": {
            "source": "db_inventory",
            "inventory_total_expected": inventory_total_expected,
            "note": "DB-derived subset report; not a fresh full pipeline run.",
        },
        "total_entries": len(metrics_list),
        "total_duration_s": 0.0,
        "aggregates": aggregates,
        "per_entry": [_entry_metrics_to_json(metrics) for metrics in metrics_list],
    }


def _entry_metrics_to_json(metrics: EntryMetrics) -> Mapping[str, object]:
    """Serialize one entry metric using the layer-3 report shape."""
    return {
        "entry_id": metrics.entry_id,
        "gene_symbol": metrics.gene_symbol,
        "classification": metrics.classification,
        "moi": metrics.moi,
        "run_id": metrics.run_id,
        "status_url": metrics.status_url,
        "pipeline_status": metrics.pipeline_status,
        "error_message": metrics.error_message,
        "last_pipeline_status": metrics.last_pipeline_status,
        "last_current_phase": metrics.last_current_phase,
        "duration_s": metrics.duration_s,
        "evidence_count": metrics.evidence_count,
        "found_rate": metrics.found_rate,
        "grounding_rate": metrics.grounding_rate,
        "standardization_accuracy": metrics.standardization_accuracy,
        "track_consistency": metrics.track_consistency,
        "field_matches": [_field_match_to_json(field_match) for field_match in metrics.field_matches],
        "entity_matches": metrics.entity_matches,
    }


def _field_match_to_json(field_match: FieldMatch) -> Mapping[str, object]:
    """Serialize one field-match result."""
    return {
        "field_id": field_match.field_id,
        "expected": field_match.expected_value,
        "matched": field_match.matched,
        "extracted": field_match.extracted_value,
        "source_span": field_match.source_span,
        "match_type": field_match.match_type,
        "extra_found_values": field_match.extra_found_values,
    }


def _load_expected_entries(
    entry_ids: Sequence[str],
    ground_truth_dir: Path = GROUND_TRUTH_DIR,
) -> list[Mapping[str, Any]]:
    """Load expected ClinGen JSON entries in the requested order."""
    entries: list[Mapping[str, Any]] = []
    for entry_id in entry_ids:
        expected_path = ground_truth_dir / entry_id / "expected.json"
        if expected_path.exists():
            entries.append(cast(Mapping[str, Any], json.loads(expected_path.read_text(encoding="utf-8"))))
    return entries


async def _query_extracted_items(session_factory, run_id: str) -> list[ExtractedRunItem]:  # noqa: ANN001
    """Load detailed run evidence items for one processing run."""
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(
                    RunEvidenceItem.field_id,
                    RunEvidenceItem.status,
                    RunEvidenceItem.value,
                    RunEvidenceItem.confidence,
                    RunEvidenceItem.source_span,
                ).where(RunEvidenceItem.processing_run_id == uuid.UUID(run_id))
            )
        ).all()
    return [
        ExtractedRunItem(
            field_id=row.field_id,
            status=row.status,
            value=row.value,
            confidence=float(row.confidence) if row.confidence else 0.0,
            source_span=row.source_span if isinstance(row.source_span, dict) else {},
        )
        for row in rows
    ]


async def build_report_from_db(
    vault_path: Path | None = None,
    requested_entry_ids: Sequence[str] | None = None,
) -> ReportPayload:
    """Build a report from the best reusable DB run for each mapped ClinGen entry."""
    load_postgres_env_from_vault(vault_path)
    rows = await query_system_run_rows()
    expected_entry_ids = load_expected_entry_ids()
    if requested_entry_ids:
        requested = set(requested_entry_ids)
        expected_entry_ids = [entry_id for entry_id in expected_entry_ids if entry_id in requested]
    inventory = build_inventory(rows, expected_entry_ids)
    expected_entries = _load_expected_entries(list(inventory.best_by_entry))

    engine = build_async_engine()
    session_factory = async_session_factory(engine)
    try:
        metrics_list: list[EntryMetrics] = []
        for entry in expected_entries:
            entry_id = str(entry["entry_id"])
            run_row = inventory.best_by_entry[entry_id]
            evidence_metrics = await query_evidence_metrics(session_factory, run_row.processing_run_id)
            extracted_items = await _query_extracted_items(session_factory, run_row.processing_run_id)
            async with session_factory() as session:
                entity_matches = await compare_entity_standardization(
                    session,
                    run_row.processing_run_id,
                    cast(dict[str, str], entry.get("expected_standardization", {})),
                )
                track_result = await compare_track_consistency(session, run_row.processing_run_id)
            metrics_list.append(
                build_entry_metrics_from_run(
                    entry,
                    run_row,
                    extracted_items,
                    found_rate=evidence_metrics.found_rate,
                    grounding_rate=evidence_metrics.source_grounding.grounding_rate,
                    entity_matches=entity_matches,
                    track_consistency=float(track_result.get("consistency", 0.0)),
                )
            )
    finally:
        await engine.dispose()

    return build_report_payload(metrics_list, inventory_total_expected=inventory.total_expected)


def write_report(report: ReportPayload, reports_dir: Path = REPORTS_DIR) -> Path:
    """Persist a DB-derived layer-3 report."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    report_path = reports_dir / f"eval_db_inventory_{ts}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report_path


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path, default=None)
    parser.add_argument("--entries", nargs="+", default=None)
    args = parser.parse_args()

    report = asyncio.run(build_report_from_db(args.vault, args.entries))
    report_path = write_report(report)
    overall = cast(Mapping[str, object], cast(Mapping[str, object], report["aggregates"])["overall"])
    print(
        f"REPORT: {report_path} N={report['total_entries']}/{report['config']['inventory_total_expected']} "
        f"P={overall['precision']} R={overall['recall']} F1={overall['f1']}"
    )


if __name__ == "__main__":
    main()
