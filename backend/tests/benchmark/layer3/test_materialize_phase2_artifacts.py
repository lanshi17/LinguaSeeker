"""Tests for materializing Phase 2 artifacts into Layer 3 ground truth."""

from __future__ import annotations

import json
from pathlib import Path

from benchmark.analysis.dataset_curation.materialize_phase2_artifacts import (
    DbEvidenceRow,
    MaterializeConfig,
    build_dual_result_from_db_rows,
    materialize_reconstructed_artifacts,
    materialize_phase2_artifacts,
)
from src.core.evidence_extraction.contracts import (
    DualEvidenceExtractionResult,
    EvidenceExtractionResult,
    EvidenceExtractionStatus,
    EvidenceItem,
    EvidenceStatus,
    ExtractionTarget,
    Track,
)


def _artifact(entry_id: str, gene: str = "ABCA3") -> DualEvidenceExtractionResult:
    target = ExtractionTarget(
        gene_symbol=gene,
        disease_name="interstitial lung disease due to ABCA3 deficiency",
        clingen_entry_id=entry_id,
    )
    original = EvidenceExtractionResult(
        status=EvidenceExtractionStatus.COMPLETED,
        document_id="doc-1",
        track=Track.ORIGINAL,
        extraction_target=target,
        evidence_items=[
            EvidenceItem(
                field_id="A.gene_symbol",
                category="A",
                field_name="Gene symbol",
                status=EvidenceStatus.FOUND,
                value=gene,
                confidence=0.9,
            )
        ],
    )
    translated = EvidenceExtractionResult(
        status=EvidenceExtractionStatus.COMPLETED,
        document_id="doc-1",
        track=Track.TRANSLATED,
        extraction_target=target,
    )
    return DualEvidenceExtractionResult(
        document_id="doc-1",
        original_result=original,
        translated_result=translated,
    )


def _write_selection(ground_truth_dir: Path, entry_id: str) -> None:
    (ground_truth_dir / "selection.json").write_text(
        json.dumps([{"entry_id": entry_id, "gene_symbol": "ABCA3"}]),
        encoding="utf-8",
    )
    (ground_truth_dir / entry_id).mkdir(parents=True)


def test_materializer_copies_matching_phase2_artifact(tmp_path: Path) -> None:
    pipeline_root = tmp_path / "pipeline"
    ground_truth_dir = tmp_path / "ground_truth"
    run_phase2_dir = pipeline_root / "run-1" / "phase_2"
    run_phase2_dir.mkdir(parents=True)
    ground_truth_dir.mkdir()
    _write_selection(ground_truth_dir, "clingen_002")
    artifact_path = run_phase2_dir / "extraction_result.json"
    artifact_path.write_text(_artifact("clingen_002").model_dump_json(), encoding="utf-8")

    report = materialize_phase2_artifacts(
        MaterializeConfig(
            pipeline_root=pipeline_root,
            ground_truth_dir=ground_truth_dir,
            entry_ids=("clingen_002",),
            write=True,
        )
    )

    output_path = ground_truth_dir / "clingen_002" / "preprocessed" / "phase_2" / "extraction_result.json"
    assert output_path.exists()
    assert report.materialized_count == 1
    assert report.rows[0].entry_id == "clingen_002"
    assert report.rows[0].status == "materialized"
    copied = DualEvidenceExtractionResult.model_validate_json(output_path.read_text(encoding="utf-8"))
    assert copied.original_result.extraction_target is not None
    assert copied.original_result.extraction_target.clingen_entry_id == "clingen_002"


def test_materializer_dry_run_does_not_write(tmp_path: Path) -> None:
    pipeline_root = tmp_path / "pipeline"
    ground_truth_dir = tmp_path / "ground_truth"
    run_phase2_dir = pipeline_root / "run-1" / "phase_2"
    run_phase2_dir.mkdir(parents=True)
    ground_truth_dir.mkdir()
    _write_selection(ground_truth_dir, "clingen_002")
    (run_phase2_dir / "extraction_result.json").write_text(
        _artifact("clingen_002").model_dump_json(),
        encoding="utf-8",
    )

    report = materialize_phase2_artifacts(
        MaterializeConfig(
            pipeline_root=pipeline_root,
            ground_truth_dir=ground_truth_dir,
            write=False,
        )
    )

    output_path = ground_truth_dir / "clingen_002" / "preprocessed" / "phase_2" / "extraction_result.json"
    assert not output_path.exists()
    assert report.rows[0].status == "would_materialize"


def test_materializer_reports_missing_entries(tmp_path: Path) -> None:
    pipeline_root = tmp_path / "pipeline"
    ground_truth_dir = tmp_path / "ground_truth"
    pipeline_root.mkdir()
    ground_truth_dir.mkdir()
    _write_selection(ground_truth_dir, "clingen_002")

    report = materialize_phase2_artifacts(
        MaterializeConfig(
            pipeline_root=pipeline_root,
            ground_truth_dir=ground_truth_dir,
            entry_ids=("clingen_002",),
            write=False,
        )
    )

    assert report.materialized_count == 0
    assert report.rows[0].entry_id == "clingen_002"
    assert report.rows[0].status == "missing_artifact"


def test_materializer_reports_already_materialized_destination(tmp_path: Path) -> None:
    pipeline_root = tmp_path / "pipeline"
    ground_truth_dir = tmp_path / "ground_truth"
    run_phase2_dir = pipeline_root / "run-1" / "phase_2"
    run_phase2_dir.mkdir(parents=True)
    ground_truth_dir.mkdir(exist_ok=True)
    _write_selection(ground_truth_dir, "clingen_002")
    destination_dir = ground_truth_dir / "clingen_002" / "preprocessed" / "phase_2"
    destination_dir.mkdir(parents=True)
    artifact = _artifact("clingen_002").model_dump_json()
    (run_phase2_dir / "extraction_result.json").write_text(artifact, encoding="utf-8")
    (destination_dir / "extraction_result.json").write_text(artifact, encoding="utf-8")

    report = materialize_phase2_artifacts(
        MaterializeConfig(
            pipeline_root=pipeline_root,
            ground_truth_dir=ground_truth_dir,
            entry_ids=("clingen_002",),
            write=False,
        )
    )

    assert report.rows[0].status == "already_materialized"


def test_build_dual_result_from_db_rows_reconstructs_tracks_and_target() -> None:
    original_item = _artifact("clingen_002").original_result.evidence_items[0]
    translated_item = EvidenceItem(
        field_id="B.disease_diagnosis",
        category="B",
        field_name="Disease diagnosis",
        status=EvidenceStatus.FOUND,
        value="interstitial lung disease due to ABCA3 deficiency",
        confidence=0.8,
    )

    result = build_dual_result_from_db_rows(
        entry_id="clingen_002",
        gene_symbol="ABCA3",
        disease_name="interstitial lung disease due to ABCA3 deficiency",
        processing_run_id="run-db",
        source_document_id="source-db",
        rows=(
            DbEvidenceRow(track="original", raw_payload=original_item.model_dump(mode="json")),
            DbEvidenceRow(track="translated", raw_payload=translated_item.model_dump(mode="json")),
        ),
    )

    assert result.document_id == "source-db"
    assert result.original_result.extraction_target is not None
    assert result.original_result.extraction_target.clingen_entry_id == "clingen_002"
    assert result.original_result.evidence_items[0].value == "ABCA3"
    assert result.translated_result.evidence_items[0].field_id == "B.disease_diagnosis"


def test_materialize_reconstructed_artifacts_writes_dual_result(tmp_path: Path) -> None:
    ground_truth_dir = tmp_path / "ground_truth"
    ground_truth_dir.mkdir()
    _write_selection(ground_truth_dir, "clingen_002")
    result = _artifact("clingen_002")

    report = materialize_reconstructed_artifacts(
        MaterializeConfig(ground_truth_dir=ground_truth_dir, write=True),
        {"clingen_002": result},
    )

    output_path = ground_truth_dir / "clingen_002" / "preprocessed" / "phase_2" / "extraction_result.json"
    assert output_path.exists()
    assert report.rows[0].status == "materialized"
    restored = DualEvidenceExtractionResult.model_validate_json(output_path.read_text(encoding="utf-8"))
    assert restored.original_result.evidence_items[0].value == "ABCA3"


def test_materialize_reconstructed_artifacts_does_not_overwrite_different_existing_file(tmp_path: Path) -> None:
    ground_truth_dir = tmp_path / "ground_truth"
    ground_truth_dir.mkdir()
    _write_selection(ground_truth_dir, "clingen_002")
    output_path = ground_truth_dir / "clingen_002" / "preprocessed" / "phase_2" / "extraction_result.json"
    output_path.parent.mkdir(parents=True)
    output_path.write_text(_artifact("clingen_002", gene="OLD").model_dump_json(), encoding="utf-8")

    report = materialize_reconstructed_artifacts(
        MaterializeConfig(ground_truth_dir=ground_truth_dir, write=True),
        {"clingen_002": _artifact("clingen_002", gene="ABCA3")},
    )

    assert report.rows[0].status == "existing_artifact_differs"
    restored = DualEvidenceExtractionResult.model_validate_json(output_path.read_text(encoding="utf-8"))
    assert restored.original_result.evidence_items[0].value == "OLD"
