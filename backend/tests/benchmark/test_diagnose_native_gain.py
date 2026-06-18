"""Tests for native-language gain diagnostics."""
from __future__ import annotations

import json
from pathlib import Path

from benchmark.analysis.diagnostics.native_gain import (
    build_native_gain_diagnostics,
    compare_dual_track_file,
    format_native_gain_diagnostics,
)


def _write_extraction_result(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "original_result": {
                    "evidence_items": [
                        {"field_id": "A.gene_symbol", "status": "found", "value": "MECP2"},
                        {"field_id": "B.disease_diagnosis", "status": "found", "value": "Rett syndrome"},
                    ]
                },
                "translated_result": {
                    "evidence_items": [
                        {"field_id": "A.gene_symbol", "status": "found", "value": "MECP2"},
                        {"field_id": "A.gene_disease_relationship", "status": "found", "value": "causative"},
                    ]
                },
            }
        ),
        encoding="utf-8",
    )


def test_compare_dual_track_file_counts_original_translated_and_shared(tmp_path) -> None:
    extraction_path = tmp_path / "zh" / "doc_001" / "extraction_result.json"
    _write_extraction_result(extraction_path)

    row = compare_dual_track_file(extraction_path, lang="zh")

    assert row.lang == "zh"
    assert row.document_id == "doc_001"
    assert row.original_count == 2
    assert row.translated_count == 2
    assert row.shared_count == 1
    assert row.original_only_count == 1
    assert row.translated_only_count == 1


def test_build_native_gain_diagnostics_filters_languages_and_limit(tmp_path) -> None:
    _write_extraction_result(tmp_path / "zh" / "doc_001" / "extraction_result.json")
    _write_extraction_result(tmp_path / "ja" / "doc_002" / "extraction_result.json")
    _write_extraction_result(tmp_path / "ru" / "doc_003" / "extraction_result.json")

    diagnostics = build_native_gain_diagnostics(tmp_path, langs=("zh", "ja"), limit=1)

    assert diagnostics.files_discovered == 3
    assert diagnostics.files_analyzed == 1
    assert diagnostics.rows[0].lang == "ja"
    assert diagnostics.total_original_only == 1
    assert diagnostics.total_translated_only == 1
    assert not diagnostics.missing_dual_track_data


def test_build_native_gain_diagnostics_flags_missing_dual_track_data(tmp_path) -> None:
    (tmp_path / "zh").mkdir()
    (tmp_path / "zh" / "native.pdf").write_bytes(b"%PDF")

    diagnostics = build_native_gain_diagnostics(tmp_path, langs=("zh",), limit=None)

    assert diagnostics.files_discovered == 0
    assert diagnostics.files_analyzed == 0
    assert diagnostics.missing_dual_track_data


def test_format_native_gain_diagnostics_reports_missing_data(tmp_path) -> None:
    diagnostics = build_native_gain_diagnostics(tmp_path, langs=("zh",), limit=None)

    output = format_native_gain_diagnostics(diagnostics)

    assert "files_analyzed=0" in output
    assert "missing dual-track extraction_result.json" in output
