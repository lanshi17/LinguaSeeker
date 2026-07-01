"""Tests for reproducible BIBM G1 decision reporting."""

from __future__ import annotations

from pathlib import Path

from benchmark.analysis.diagnostics.grounding import GroundingDiagnostics
from benchmark.analysis.diagnostics.native_gain import NativeGainDiagnostics
from benchmark.analysis.diagnostics.baselines import BaselineComparison, ComparisonRow
from benchmark.analysis.paper_artifacts.g1_decision import (
    build_g1_decision,
    format_g1_decision,
    g1_decision_to_payload,
)
from benchmark.analysis.dataset_curation.inventory_system_runs import SystemRunInventory


def _comparison() -> BaselineComparison:
    return BaselineComparison(
        rows=[
            ComparisonRow(
                label="SYSTEM",
                report_path=Path("eval_db_inventory.json"),
                total_entries=3,
                precision=0.8,
                recall=1.0,
                f1=0.8889,
            ),
            ComparisonRow(
                label="B0",
                report_path=Path("baseline_b0.json"),
                total_entries=3,
                precision=0.8889,
                recall=1.0,
                f1=0.9412,
                matched_to_system_entries=True,
            ),
            ComparisonRow(
                label="B4",
                report_path=Path("baseline_b4.json"),
                total_entries=3,
                precision=0.8889,
                recall=1.0,
                f1=0.9412,
                matched_to_system_entries=True,
            ),
        ]
    )


def _inventory() -> SystemRunInventory:
    return SystemRunInventory(
        total_expected=30,
        best_by_entry={},
        missing_entry_ids=[f"clingen_{index:03d}" for index in range(3, 30)],
        unmapped_count=22,
    )


def _grounding() -> GroundingDiagnostics:
    return GroundingDiagnostics(
        report_path=Path("eval_db_inventory.json"),
        total_entries=3,
        entries_with_grounding_rate=3,
        mean_grounding_rate=0.0,
        span_evidence_count=9,
        valid_span_count=9,
        invalid_span_count=0,
        citation_validity_rate=1.0,
        hallucinated_citation_rate=0.0,
        grounded_matched=8,
        grounded_wrong_or_over=2,
        ungrounded_matched=0,
        ungrounded_wrong_or_over=0,
        missing_span_evidence=False,
    )


def _native_gain() -> NativeGainDiagnostics:
    return NativeGainDiagnostics(
        root=Path("rett"),
        requested_langs=(),
        files_discovered=0,
        files_analyzed=0,
        rows=[],
        total_original_only=0,
        total_translated_only=0,
        total_shared=0,
        missing_dual_track_data=True,
    )


def test_build_g1_decision_marks_main_paper_no_go_when_system_loses_to_matched_baselines() -> None:
    decision = build_g1_decision(_comparison(), _inventory(), _grounding(), _native_gain())

    assert decision.recommendation == "owner_decision_required"
    assert decision.main_paper_ready is False
    assert decision.directions[0].direction == "A_structured_extraction"
    assert decision.directions[0].signal == "no_go"
    assert "SYSTEM F1=0.8889" in decision.directions[0].key_numbers
    assert "best matched baseline B0/B4 F1=0.9412" in decision.directions[0].key_numbers


def test_build_g1_decision_classifies_unavailable_native_gain_and_weak_grounding_signal() -> None:
    decision = build_g1_decision(_comparison(), _inventory(), _grounding(), _native_gain())

    by_direction = {row.direction: row for row in decision.directions}
    assert by_direction["B_native_gain"].signal == "not_evaluable"
    assert by_direction["C_grounding_traceability"].signal == "weak_feasibility_signal"
    assert "CVR=1.0" in by_direction["C_grounding_traceability"].key_numbers
    assert "span_evidence=9" in by_direction["C_grounding_traceability"].key_numbers


def test_g1_decision_payload_and_format_include_traceable_artifact_paths() -> None:
    decision = build_g1_decision(_comparison(), _inventory(), _grounding(), _native_gain())

    payload = g1_decision_to_payload(decision)
    formatted = format_g1_decision(decision)

    assert payload["main_paper_ready"] is False
    assert payload["directions"][0]["signal"] == "no_go"
    assert "system_report" in payload["evidence"]
    assert "eval_db_inventory.json" in formatted
    assert "owner_decision_required" in formatted
