"""Tests for the LOO learned arbitrator policy evaluation."""
from __future__ import annotations

import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from benchmark.analysis.arbitrator.dataset import (
    CandidateSample,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.reconcile.features import (
    CandidateFeatureVector,
)


def _make_sample(
    entry_id: str = "clingen_000",
    field_id: str = "A.gene_symbol",
    label: int = 1,
    feature_override: dict[str, float] | None = None,
) -> CandidateSample:
    defaults = {
        "source_score": 1.0 if label == 1 else 0.5,
        "has_source": 1.0,
        "source_is_exact": 1.0 if label == 1 else 0.0,
        "source_is_corrected": 0.0,
        "span_length": 0.3,
        "confidence_score": 0.9 if label == 1 else 0.4,
        "status_is_found": 1.0,
        "status_is_not_found": 0.0,
        "agreement_score": 1.0 if label == 1 else 0.0,
        "verifier_support_score": 0.8 if label == 1 else 0.3,
        "target_specificity_score": 0.6,
        "contradiction_penalty": 0.0 if label == 1 else 0.3,
        "no_contradiction": 1.0 if label == 1 else 0.7,
        "field_is_gene": 1.0,
        "field_is_disease": 0.0,
        "field_is_relationship": 0.0,
        "track_is_original": 1.0,
        "source_x_agreement": 1.0 if label == 1 else 0.0,
        "verifier_x_no_contradiction": 0.8 if label == 1 else 0.21,
        "target_x_verifier": 0.48,
        "source_x_verifier": 0.8 if label == 1 else 0.15,
    }
    if feature_override:
        defaults.update(feature_override)
    features = CandidateFeatureVector(**defaults)
    return CandidateSample(
        entry_id=entry_id,
        field_id=field_id,
        track="original",
        normalized_value="test" if label == 1 else "wrong",
        label=label,
        features=features,
        span_id="span-1",
        source_snippet_hash="abc123",
        selected_by_contextual=label == 1,
    )


class TestTrainFold:
    def test_train_fold_produces_model(self) -> None:
        from benchmark.analysis.arbitrator.policy_eval import _train_fold

        samples = [
            _make_sample(label=1),
            _make_sample(label=0),
            _make_sample(label=1),
            _make_sample(label=0),
            _make_sample(label=1),
            _make_sample(label=0),
        ]
        model, scaler, coefficients = _train_fold(samples, c_reg=1.0)
        assert isinstance(model, LogisticRegression)
        assert isinstance(scaler, StandardScaler)
        assert len(coefficients) == 21
        assert all(isinstance(v, float) for v in coefficients.values())

    def test_train_fold_predicts(self) -> None:
        from benchmark.analysis.arbitrator.policy_eval import _train_fold

        np.random.seed(42)
        pos_samples = [_make_sample(label=1) for _ in range(10)]
        neg_samples = [_make_sample(label=0) for _ in range(10)]
        model, scaler, _ = _train_fold(pos_samples + neg_samples)

        test_pos = _make_sample(label=1)
        test_neg = _make_sample(label=0)
        X = np.array([test_pos.features.to_list(), test_neg.features.to_list()])
        X_scaled = scaler.transform(X)
        probs = model.predict_proba(X_scaled)[:, 1]
        assert probs[0] > probs[1]


class TestEntryF1:
    def test_entry_f1_all_matched(self) -> None:
        from benchmark.analysis.arbitrator.policy_eval import _entry_f1
        from benchmark.core import EntryMetrics, FieldMatch

        metrics = EntryMetrics(
            entry_id="test",
            gene_symbol="GENE",
            classification="Definitive",
            moi="AD",
            language="en",
            field_matches=[
                FieldMatch(
                    field_id="A.gene_symbol",
                    expected_value="GENE",
                    matched=True,
                    extracted_value="GENE",
                    source_span=None,
                    match_type="exact",
                    extra_found_values=[],
                ),
            ],
        )
        assert _entry_f1(metrics) == 1.0


class TestGateA:
    def test_gate_a_f1_gain(self) -> None:
        from benchmark.analysis.arbitrator.policy_eval import _check_gate_a, PolicyEvalReport

        report = PolicyEvalReport(
            folds=[],
            contextual_overall_f1=0.94,
            learned_overall_f1=0.95,
            delta_f1=0.01,
            per_field_contextual_f1={},
            per_field_learned_f1={},
            relationship_error_reduction=None,
        )
        assert _check_gate_a(report) is True

    def test_gate_a_fails_below_threshold(self) -> None:
        from benchmark.analysis.arbitrator.policy_eval import _check_gate_a, PolicyEvalReport

        report = PolicyEvalReport(
            folds=[],
            contextual_overall_f1=0.9474,
            learned_overall_f1=0.9480,
            delta_f1=0.0006,
            per_field_contextual_f1={},
            per_field_learned_f1={},
            relationship_error_reduction=None,
        )
        assert _check_gate_a(report) is False

    def test_gate_a_relationship_reduction(self) -> None:
        from benchmark.analysis.arbitrator.policy_eval import _check_gate_a, PolicyEvalReport

        report = PolicyEvalReport(
            folds=[],
            contextual_overall_f1=0.9474,
            learned_overall_f1=0.9474,
            delta_f1=0.0,
            per_field_contextual_f1={"A.gene_disease_relationship": 0.85},
            per_field_learned_f1={"A.gene_disease_relationship": 0.89},
            relationship_error_reduction=0.267,
        )
        assert _check_gate_a(report) is True


class TestLOOIntegration:
    def test_loo_runs_on_real_data(self) -> None:
        from benchmark.analysis.arbitrator.policy_eval import run_loo_evaluation
        from benchmark.core.paths import GROUND_TRUTH_CLINGEN_ROOT

        if not GROUND_TRUTH_CLINGEN_ROOT.exists():
            pytest.skip("clingen ground_truth directory not available")

        report = run_loo_evaluation(GROUND_TRUTH_CLINGEN_ROOT)
        assert len(report.folds) > 0
        assert report.contextual_overall_f1 > 0
        assert isinstance(report.learned_overall_f1, float)
        assert isinstance(report.delta_f1, float)
