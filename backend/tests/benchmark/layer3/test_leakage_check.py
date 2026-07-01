"""Tests for the learned arbitrator leakage audit."""

from __future__ import annotations

import json
from pathlib import Path

from benchmark.analysis.dataset_curation.leakage_check import (
    LeakageAuditReport,
    check_artifact_leakage,
    check_context_pack_no_gold_labels,
    check_fold_isolation,
    check_reconcile_source_isolation,
    check_source_span_provenance,
    run_full_audit,
)


def _make_ground_truth_dir(
    tmp_path: Path,
    *,
    inject_leakage: bool = False,
    omit_span_id: bool = False,
) -> Path:
    gt_dir = tmp_path / "ground_truth"
    entry_dir = gt_dir / "clingen_000"
    phase2_dir = entry_dir / "preprocessed" / "phase_2"
    phase2_dir.mkdir(parents=True)

    artifact: dict[str, object] = {
        "document_id": "test-doc",
        "original_result": {
            "evidence_items": [
                {
                    "field_id": "A.gene_symbol",
                    "status": "found",
                    "value": "TEST",
                    "confidence": 0.9,
                    "source": (
                        {"text_snippet": "test span"}
                        if omit_span_id
                        else {"span_id": "span-001", "text_snippet": "test span"}
                    ),
                },
            ],
        },
        "translated_result": {"evidence_items": []},
    }
    if inject_leakage:
        artifact["expected_evidence"] = [{"field_id": "A.gene_symbol", "value": "TEST"}]
    (phase2_dir / "extraction_result.json").write_text(json.dumps(artifact), encoding="utf-8")
    return gt_dir


class TestArtifactLeakage:
    def test_clean_artifact_passes(self, tmp_path: Path) -> None:
        gt_dir = _make_ground_truth_dir(tmp_path)
        result = check_artifact_leakage(gt_dir)
        assert result.passed is True
        assert result.check_name == "artifact_leakage"

    def test_leaky_artifact_fails(self, tmp_path: Path) -> None:
        gt_dir = _make_ground_truth_dir(tmp_path, inject_leakage=True)
        result = check_artifact_leakage(gt_dir)
        assert result.passed is False
        assert "expected_evidence" in result.detail


class TestReconcileSourceIsolation:
    def test_real_reconcile_dir_passes(self) -> None:
        result = check_reconcile_source_isolation()
        assert result.passed is True

    def test_leaky_source_fails(self, tmp_path: Path) -> None:
        fake_dir = tmp_path / "reconcile"
        fake_dir.mkdir()
        (fake_dir / "leaky.py").write_text("from benchmark.layer3.evaluate import compare_evidence\n", encoding="utf-8")
        result = check_reconcile_source_isolation(fake_dir)
        assert result.passed is False
        assert "evaluate" in result.detail


class TestContextPackNoGoldLabels:
    def test_real_context_pack_passes(self) -> None:
        result = check_context_pack_no_gold_labels()
        assert result.passed is True


class TestFoldIsolation:
    def test_isolated_fold_passes(self) -> None:
        training = {"clingen_000", "clingen_001", "clingen_002"}
        result = check_fold_isolation(training, "clingen_003")
        assert result.passed is True

    def test_leaked_fold_fails(self) -> None:
        training = {"clingen_000", "clingen_001", "clingen_002"}
        result = check_fold_isolation(training, "clingen_001")
        assert result.passed is False


class TestSourceSpanProvenance:
    def test_spans_with_span_id_pass(self, tmp_path: Path) -> None:
        gt_dir = _make_ground_truth_dir(tmp_path)
        result = check_source_span_provenance(gt_dir)
        assert result.passed is True

    def test_spans_without_span_id_fail(self, tmp_path: Path) -> None:
        gt_dir = _make_ground_truth_dir(tmp_path, omit_span_id=True)
        result = check_source_span_provenance(gt_dir)
        assert result.passed is False


class TestFullAudit:
    def test_full_audit_returns_report(self) -> None:
        report = run_full_audit()
        assert isinstance(report, LeakageAuditReport)
        assert len(report.checks) >= 4
        for check in report.checks:
            assert check.check_name
