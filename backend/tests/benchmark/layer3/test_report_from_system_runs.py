"""Tests for DB-derived layer-3 report construction."""
from __future__ import annotations

from benchmark.layer3.analysis.inventory_system_runs import SystemRunRow
from benchmark.layer3.analysis.report_from_system_runs import (
    ExtractedRunItem,
    build_entry_metrics_from_run,
    build_report_payload,
)


def test_build_entry_metrics_from_run_preserves_source_spans() -> None:
    entry = {
        "entry_id": "clingen_002",
        "gene_symbol": "ABCA3",
        "classification": "Definitive",
        "moi": "AR",
        "expected_evidence": [
            {"field_id": "A.gene_symbol", "value": "ABCA3"},
            {"field_id": "A.gene_disease_relationship", "value": "causative"},
        ],
    }
    run_row = SystemRunRow(
        processing_run_id="run-1",
        source_document_id="source-1",
        pipeline_status="awaiting_review",
        source_key="clingen_002.md|clingen=clingen_002",
        evidence_count=2,
        found_count=2,
        source_span_count=2,
        updated_at="2026-06-12 10:00:00+08",
    )
    source_span = {"text_snippet": "ABCA3 caused disease", "start_offset": 0, "end_offset": 20}
    metrics = build_entry_metrics_from_run(
        entry,
        run_row,
        extracted_items=[
            ExtractedRunItem(
                field_id="A.gene_symbol",
                status="found",
                value={"value": "ABCA3"},
                confidence=0.9,
                source_span=source_span,
            ),
            ExtractedRunItem(
                field_id="A.gene_disease_relationship",
                status="found",
                value={"value": "causative"},
                confidence=0.8,
                source_span=source_span,
            ),
        ],
        found_rate=1.0,
        grounding_rate=1.0,
        entity_matches={},
        track_consistency=0.0,
    )

    assert metrics.entry_id == "clingen_002"
    assert metrics.run_id == "run-1"
    assert metrics.pipeline_status == "awaiting_review"
    assert metrics.evidence_count == 2
    assert all(field_match.matched for field_match in metrics.field_matches)
    assert metrics.field_matches[0].source_span == source_span


def test_build_report_payload_computes_aggregates() -> None:
    entry = {
        "entry_id": "clingen_002",
        "gene_symbol": "ABCA3",
        "classification": "Definitive",
        "moi": "AR",
        "expected_evidence": [{"field_id": "A.gene_symbol", "value": "ABCA3"}],
    }
    run_row = SystemRunRow(
        processing_run_id="run-1",
        source_document_id="source-1",
        pipeline_status="awaiting_review",
        source_key="clingen_002.md|clingen=clingen_002",
        evidence_count=1,
        found_count=1,
        source_span_count=1,
        updated_at="2026-06-12 10:00:00+08",
    )
    metrics = build_entry_metrics_from_run(
        entry,
        run_row,
        extracted_items=[
            ExtractedRunItem(
                field_id="A.gene_symbol",
                status="found",
                value={"value": "ABCA3"},
                confidence=0.9,
                source_span={"text_snippet": "ABCA3", "start_offset": 0, "end_offset": 5},
            )
        ],
        found_rate=1.0,
        grounding_rate=1.0,
        entity_matches={},
        track_consistency=0.0,
    )

    report = build_report_payload([metrics], inventory_total_expected=30)

    assert report["total_entries"] == 1
    assert report["config"]["source"] == "db_inventory"
    assert report["config"]["inventory_total_expected"] == 30
    assert report["aggregates"]["overall"]["f1"] == 1.0
    assert report["per_entry"][0]["field_matches"][0]["source_span"]["text_snippet"] == "ABCA3"
