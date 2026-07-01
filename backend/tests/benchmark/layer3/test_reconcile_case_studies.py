"""Tests for reconcile ablation case-study extraction."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from benchmark.analysis.reconcile.case_studies import (
    build_case_study_report,
    format_case_study_report,
)


def _match(
    *,
    field_id: str,
    matched: bool,
    extracted: str | None,
    match_type: str,
    extra_found_values: list[str] | None = None,
) -> Mapping[str, object]:
    return {
        "field_id": field_id,
        "expected": "expected",
        "matched": matched,
        "extracted": extracted,
        "match_type": match_type,
        "source_span": {
            "text_snippet": "A traceable source sentence.",
            "start_offset": 0,
            "end_offset": 28,
            "source_precision": "corrected",
        },
        "extra_found_values": extra_found_values or [],
    }


def _entry(entry_id: str, field_matches: list[Mapping[str, object]]) -> Mapping[str, object]:
    return {
        "entry_id": entry_id,
        "pipeline_status": "completed",
        "field_matches": field_matches,
    }


def _write_report(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "evaluation_id": "reconcile_ablation_test",
                "strategies": [
                    {
                        "strategy": "dual_union",
                        "total_entries": 1,
                        "per_entry": [
                            _entry(
                                "clingen_000",
                                [
                                    _match(
                                        field_id="A.gene_symbol",
                                        matched=False,
                                        extracted="BRCA2",
                                        match_type="wrong_value",
                                    ),
                                    _match(
                                        field_id="B.disease_diagnosis",
                                        matched=True,
                                        extracted="Breast cancer",
                                        match_type="exact",
                                        extra_found_values=["Breast carcinoma"],
                                    ),
                                ],
                            )
                        ],
                    },
                    {
                        "strategy": "context_verifier_reconcile",
                        "total_entries": 1,
                        "per_entry": [
                            _entry(
                                "clingen_000",
                                [
                                    _match(
                                        field_id="A.gene_symbol",
                                        matched=True,
                                        extracted="BRCA1",
                                        match_type="exact",
                                    ),
                                    _match(
                                        field_id="B.disease_diagnosis",
                                        matched=True,
                                        extracted="Breast cancer",
                                        match_type="exact",
                                    ),
                                ],
                            )
                        ],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


def test_build_case_study_report_extracts_corrected_fields_and_removed_extras(tmp_path: Path) -> None:
    report_path = tmp_path / "reconcile_ablation.json"
    _write_report(report_path)

    report = build_case_study_report(report_path)

    assert report.total_cases == 2
    by_type = {case.improvement_type: case for case in report.cases}
    assert by_type["field_corrected"].field_id == "A.gene_symbol"
    assert by_type["field_corrected"].baseline_extracted == "BRCA2"
    assert by_type["field_corrected"].candidate_extracted == "BRCA1"
    assert by_type["over_extraction_removed"].removed_extra_values == ("Breast carcinoma",)


def test_format_case_study_report_includes_traceable_case_summary(tmp_path: Path) -> None:
    report_path = tmp_path / "reconcile_ablation.json"
    _write_report(report_path)

    output = format_case_study_report(build_case_study_report(report_path))

    assert "cases=2" in output
    assert "field_corrected" in output
    assert "clingen_000" in output
