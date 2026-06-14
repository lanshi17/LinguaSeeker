"""Tests for ClinGen system-run inventory diagnostics."""
from __future__ import annotations

from benchmark.layer3.analysis.inventory_system_runs import (
    SystemRunRow,
    build_inventory,
    choose_best_run,
    format_inventory,
    parse_clingen_entry_id,
)


def _row(
    run_id: str,
    *,
    source_key: str | None,
    status: str = "awaiting_review",
    evidence_count: int = 0,
    found_count: int = 0,
    source_span_count: int = 0,
    updated_at: str = "2026-06-12 10:00:00+08",
) -> SystemRunRow:
    return SystemRunRow(
        processing_run_id=run_id,
        source_document_id=f"source-{run_id}",
        pipeline_status=status,
        source_key=source_key,
        evidence_count=evidence_count,
        found_count=found_count,
        source_span_count=source_span_count,
        updated_at=updated_at,
    )


def test_parse_clingen_entry_id_from_source_key() -> None:
    assert parse_clingen_entry_id("clingen_002.md|gene=ABCA3|clingen=clingen_002") == "clingen_002"
    assert parse_clingen_entry_id("clingen_014.md") == "clingen_014"
    assert parse_clingen_entry_id("5例Rett综合征样表型患儿的基因突变分析_刘文晶.pdf") is None
    assert parse_clingen_entry_id(None) is None


def test_choose_best_run_prefers_successful_run_with_more_source_spans() -> None:
    failed = _row(
        "failed-run",
        source_key="clingen_000.md|clingen=clingen_000",
        status="failed",
        evidence_count=0,
        found_count=0,
        source_span_count=0,
    )
    successful_without_spans = _row(
        "old-success",
        source_key="clingen_000.md|clingen=clingen_000",
        evidence_count=30,
        found_count=25,
        source_span_count=0,
        updated_at="2026-06-12 09:00:00+08",
    )
    successful_with_spans = _row(
        "best-success",
        source_key="clingen_000.md|clingen=clingen_000",
        evidence_count=13,
        found_count=13,
        source_span_count=13,
        updated_at="2026-06-12 11:00:00+08",
    )

    assert choose_best_run([failed, successful_without_spans, successful_with_spans]) == successful_with_spans


def test_build_inventory_maps_only_explicit_clingen_source_keys() -> None:
    rows = [
        _row(
            "clingen-run",
            source_key="clingen_001.md|gene=AARS2|clingen=clingen_001",
            evidence_count=28,
            found_count=27,
            source_span_count=27,
        ),
        _row(
            "unmapped-e2e",
            source_key=None,
            evidence_count=51,
            found_count=47,
            source_span_count=47,
        ),
    ]

    inventory = build_inventory(rows, expected_entry_ids=["clingen_000", "clingen_001", "clingen_002"])

    assert inventory.total_expected == 3
    assert inventory.mapped_count == 1
    assert inventory.missing_entry_ids == ["clingen_000", "clingen_002"]
    assert inventory.best_by_entry["clingen_001"].processing_run_id == "clingen-run"


def test_format_inventory_reports_coverage_and_best_runs() -> None:
    inventory = build_inventory(
        [
            _row(
                "best-run",
                source_key="clingen_002.md|gene=ABCA3|clingen=clingen_002",
                evidence_count=63,
                found_count=57,
                source_span_count=57,
            )
        ],
        expected_entry_ids=["clingen_000", "clingen_001", "clingen_002"],
    )

    output = format_inventory(inventory)

    assert "mapped=1/3" in output
    assert "missing=clingen_000,clingen_001" in output
    assert "clingen_002 best-run awaiting_review evidence=63 found=57 spans=57" in output
