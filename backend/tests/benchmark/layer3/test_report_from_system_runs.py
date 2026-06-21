"""Tests for DB-derived layer-3 report construction."""
from __future__ import annotations

import pytest

from benchmark.analysis.dataset_curation.inventory_system_runs import SystemRunRow
from benchmark.analysis.dataset_curation.report_from_system_runs import (
    ExtractedRunItem,
    _load_expected_entries,
    build_report_from_db,
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
        pipeline_status="completed",
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
    assert metrics.pipeline_status == "completed"
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
        pipeline_status="completed",
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


def test_load_expected_entries_uses_rett_ground_truth_dir(tmp_path) -> None:
    entry_dir = tmp_path / "rett_069"
    entry_dir.mkdir()
    (entry_dir / "expected.json").write_text(
        """
        {
          "entry_id": "rett_069",
          "gene_symbol": "MECP2",
          "disease_label": "Rett syndrome",
          "expected_evidence": [{"field_id": "A.gene_symbol", "value": "MECP2"}]
        }
        """,
        encoding="utf-8",
    )

    entries = _load_expected_entries(["rett_069"], ground_truth_dir=tmp_path)

    assert entries[0]["entry_id"] == "rett_069"
    assert entries[0]["gene_symbol"] == "MECP2"


@pytest.mark.asyncio
async def test_build_report_from_db_passes_rett_inventory_parameters(monkeypatch, tmp_path) -> None:
    captured = {}

    async def fake_query_system_run_rows():
        return [
            SystemRunRow(
                processing_run_id="00000000-0000-0000-0000-000000000001",
                source_document_id="00000000-0000-0000-0000-000000000002",
                pipeline_status="completed",
                source_key="rett_069.md|rett=rett_069",
                evidence_count=0,
                found_count=0,
                source_span_count=0,
                updated_at="2026-06-21 10:00:00+08",
            )
        ]

    def fake_load_expected_entry_ids(ground_truth_dir):
        captured["ground_truth_dir"] = ground_truth_dir
        return ["rett_069"]

    def fake_build_inventory(rows, expected_entry_ids, *, entry_id_key, entry_id_pattern):
        captured["entry_id_key"] = entry_id_key
        captured["entry_id_pattern"] = entry_id_pattern
        return type(
            "Inventory",
            (),
            {
                "best_by_entry": {},
                "total_expected": len(expected_entry_ids),
            },
        )()

    monkeypatch.setattr(
        "benchmark.analysis.dataset_curation.report_from_system_runs.query_system_run_rows",
        fake_query_system_run_rows,
    )
    monkeypatch.setattr(
        "benchmark.analysis.dataset_curation.report_from_system_runs.load_expected_entry_ids",
        fake_load_expected_entry_ids,
    )
    monkeypatch.setattr(
        "benchmark.analysis.dataset_curation.report_from_system_runs.build_inventory",
        fake_build_inventory,
    )

    report = await build_report_from_db(
        ground_truth_dir=tmp_path,
        entry_id_key="rett",
        entry_id_pattern=r"\b(rett_\d+)\b",
    )

    assert captured == {
        "ground_truth_dir": tmp_path,
        "entry_id_key": "rett",
        "entry_id_pattern": r"\b(rett_\d+)\b",
    }
    assert report["total_entries"] == 0
    assert report["config"]["inventory_total_expected"] == 1
