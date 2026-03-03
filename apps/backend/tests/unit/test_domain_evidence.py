from types import SimpleNamespace
from typing import Any, Dict

import pytest

from src.domain.evidence import aggregator as aggregator_module
from src.domain.evidence import classifier as classifier_module
from src.domain.evidence import evaluation_framework as framework_module
from src.domain.evidence import tools as tools_module


class FakeRecord:
    def __init__(self, **kwargs: object) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


def test_odds_path_calculator_valid() -> None:
    result = tools_module.OddsPath_Calculator(0.2, 0.8)
    assert result == pytest.approx((0.8 * 0.8) / (0.2 * 0.2))


def test_odds_path_calculator_invalid() -> None:
    assert tools_module.OddsPath_Calculator(1.2, 0.5) == -1.0


def test_odds_path_calculator_boundary_clamp() -> None:
    result = tools_module.OddsPath_Calculator(0.0, 1.0)
    assert result > 0


def test_determine_evidence_strength_from_oddspath() -> None:
    assert tools_module.determine_evidence_strength_from_oddspath(0.02) == "BS3"
    assert tools_module.determine_evidence_strength_from_oddspath(0.1) == "BS3_moderate"
    assert tools_module.determine_evidence_strength_from_oddspath(0.3) == "BS3_supporting"
    assert tools_module.determine_evidence_strength_from_oddspath(1.0) == "BS3_supporting"
    assert tools_module.determine_evidence_strength_from_oddspath(3.0) == "PS3_supporting"
    assert tools_module.determine_evidence_strength_from_oddspath(5.0) == "PS3_moderate"
    assert tools_module.determine_evidence_strength_from_oddspath(20.0) == "PS3"
    assert tools_module.determine_evidence_strength_from_oddspath(400.0) == "PS3_very_strong"


def test_determine_strength_by_oddpath_generic() -> None:
    assert framework_module.determine_strength_by_oddpath(0.001) == "Very Strong"
    assert framework_module.determine_strength_by_oddpath(0.01) == "Strong"
    assert framework_module.determine_strength_by_oddpath(0.1) == "Moderate"
    assert framework_module.determine_strength_by_oddpath(1.5) == "Supporting"
    assert framework_module.determine_strength_by_oddpath(10.0) == "Moderate"
    assert framework_module.determine_strength_by_oddpath(100.0) == "Strong"
    assert framework_module.determine_strength_by_oddpath(400.0) == "Very Strong"


def test_determine_evidence_strength_no_ps3_bs3() -> None:
    result = framework_module.determine_evidence_strength({"assay_suitable": "no"})
    assert result["use_ps3_bs3"] is False
    assert result["strength"] == "No PS3/BS3"
    assert result["path"] == "not_applicable"


def test_determine_evidence_strength_control_count_path() -> None:
    data = {
        "assay_suitable": "yes",
        "ps3_step_3": {
            "checkpoint_3a": {
                "basic_controls_present": True,
                "replicates_used": True,
            },
            "checkpoint_3c": {"positive_controls_used": True},
        },
        "ps3_step_4": {
            "oddspath_data": {"computable": False},
            "control_count_data": {"pathogenic_count": 4, "benign_count": 8},
        },
    }
    result = framework_module.determine_evidence_strength(data)
    assert result["use_ps3_bs3"] is True
    assert result["strength"] == "Moderate"
    assert result["directional_strength"] == "PS3_moderate"
    assert result["path"] == "control_count"


def test_determine_evidence_strength_oddspath_path() -> None:
    data = {
        "assay_suitable": "yes",
        "functional_evidence_aim": "benign",
        "ps3_step_3": {
            "checkpoint_3a": {
                "basic_controls_present": True,
                "replicates_used": True,
            },
            "checkpoint_3c": {"positive_controls_used": True},
        },
        "ps3_step_4": {
            "oddspath_data": {"computable": True, "oddspath": 0.01},
        },
    }
    result = framework_module.determine_evidence_strength(data)
    assert result["use_ps3_bs3"] is True
    assert result["strength"] == "Strong"
    assert result["directional_strength"] == "BS3"
    assert result["path"] == "oddspath"


def test_evaluate_extraction_metrics() -> None:
    benchmark_items = [
        {"gene": "BRCA1", "variant": "c.68_69del", "disease": "Breast cancer", "assay_type": "reporter"},
        {"gene": "CFTR", "variant": "c.1521_1523delCTT", "disease": "CF", "assay_type": "chloride"},
    ]
    model_items = [
        {"gene": "BRCA1", "variant": "c.68_69del", "disease": "Breast cancer", "assay_type": "reporter"},
        {"gene": "TP53", "variant": "c.743G>A", "disease": "Li-Fraumeni", "assay_type": "transactivation"},
    ]
    metrics = framework_module.evaluate_extraction_metrics(benchmark_items, model_items)
    assert metrics.benchmark_total == 2
    assert metrics.model_output_total == 2
    assert metrics.correct_count == 1
    assert metrics.false_assertions == 1
    assert metrics.field_omissions == 1
    assert metrics.accuracy == 0.5


def test_determine_max_evidence_from_controls() -> None:
    assert tools_module.determine_max_evidence_from_controls(0) == "no_evidence"
    assert tools_module.determine_max_evidence_from_controls(5) == "max_supporting"
    assert tools_module.determine_max_evidence_from_controls(11) == "max_moderate"


def test_validate_ps3_steps() -> None:
    assert tools_module.validate_ps3_step1("clear")["step1_pass"] is True
    assert tools_module.validate_ps3_step1("unclear")["can_proceed"] is False
    assert tools_module.validate_ps3_step2("yes")["step2_pass"] is True
    assert tools_module.validate_ps3_step2("no")["can_proceed"] is False


def test_classifier_mappings() -> None:
    assert classifier_module.EvidenceClassifier.oddspath_to_strength(5.0) == "PS3_moderate"
    assert classifier_module.EvidenceClassifier.max_strength_from_controls(0) == "no_evidence"
    assert classifier_module.EvidenceClassifier.score_to_classification(85.0) == "Pathogenic"


def test_classifier_classify_with_fields() -> None:
    ps3_evidence = {
        "ps3_step_1": {"score": 30, "evidence_refs": ["s1"]},
        "ps3_step_2": {"score": 20, "evidence_refs": ["s2"]},
        "ps3_step_3": {"score": 20, "evidence_refs": ["s3"]},
        "ps3_step_4": {"score": 20, "final_evidence_strength": "PS3_supporting"},
    }
    extracted_fields = {"gene": {"symbol": "GENE", "confidence": 90.0}}
    result = classifier_module.EvidenceClassifier.classify(ps3_evidence, extracted_fields)
    assert result.overall_score == 90.0
    assert result.classification == "Pathogenic"
    assert result.acmg_levels == ["PP3"]
    assert result.is_valid is True
    assert result.validity_reason == "meets_threshold"
    assert set(result.supporting_evidence) == {"s1", "s2", "s3"}


def test_classifier_validate_with_arbitration() -> None:
    ps3_evidence = {
        "ps3_step_1": {"score": 20},
        "ps3_step_2": {"score": 20},
        "ps3_step_3": {"score": 20},
        "ps3_step_4": {"score": 20, "final_evidence_strength": "PS3"},
    }
    arbitration = {"arbitration_score": 90, "score_adjustment": 10, "final_decision": "approve"}
    result = classifier_module.EvidenceClassifier.validate_with_arbitration(ps3_evidence, arbitration)
    assert result["adjusted_score"] == 90.0
    assert result["final_classification"] == "Pathogenic"
    assert result["final_is_valid"] is True


def test_classifier_validity_reason_missing_fields() -> None:
    ps3_evidence: Dict[str, Any] = {
        "ps3_step_1": {"score": 0},
        "ps3_step_2": {"score": 0},
    }
    result = classifier_module.EvidenceClassifier.classify(ps3_evidence, extracted_fields=None)
    assert result.overall_score == 0.0
    assert result.is_valid is False
    assert result.validity_reason in {"missing_extractions", "no_structured_fields", "no_scoring_signal"}


def test_aggregate_variant_group(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakePostgres:
        def search_evidence_by_gene(self, *_: object, **__: object) -> list:
            return []

    monkeypatch.setattr(aggregator_module, "get_postgres_client", lambda: FakePostgres())
    engine = aggregator_module.EvidenceAggregationEngine()

    records = [
        FakeRecord(
            evidence_id=1,
            document_id=1,
            evidence_strength="PS3_supporting",
            evidence_classification="Likely Pathogenic",
            overall_confidence=80.0,
            arbitration_score=0,
            is_valid="false",
            variant_hgvs_c="c.1A>T",
            variant_hgvs_p="p.K1N",
            protein_change="p.K1N",
        ),
        FakeRecord(
            evidence_id=2,
            document_id=2,
            evidence_strength="PS3_supporting",
            evidence_classification="Likely Pathogenic",
            overall_confidence=90.0,
            arbitration_score=0,
            is_valid="true",
            variant_hgvs_c="c.1A>T",
            variant_hgvs_p="p.K1N",
            protein_change="p.K1N",
        ),
    ]

    agg = engine._aggregate_variant_group("GENE", ("c.1A>T", "p.K1N"), records)
    assert agg.document_count == 2
    assert agg.evidence_count == 2
    assert agg.valid_evidence_count == 1
    assert agg.consensus_strength == "PS3_supporting"
    assert agg.consensus_acmg_levels == ["PP3"]
    assert agg.quality_grade == "B"


def test_aggregate_by_gene(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakePostgres:
        def search_evidence_by_gene(self, *_: object, **__: object) -> list:
            return [
                SimpleNamespace(
                    evidence_id=1,
                    document_id=1,
                    evidence_strength="PS3",
                    evidence_classification="Pathogenic",
                    overall_confidence=90.0,
                    arbitration_score=0,
                    is_valid="true",
                    variant_hgvs_c="c.1A>T",
                    variant_hgvs_p="p.K1N",
                    protein_change="p.K1N",
                    gene_symbol="GENE",
                )
            ]

    monkeypatch.setattr(aggregator_module, "get_postgres_client", lambda: FakePostgres())
    engine = aggregator_module.EvidenceAggregationEngine()
    report = engine.aggregate_by_gene("GENE")
    assert report.overall_stats["total_variants"] == 1
    assert report.overall_stats["total_evidence"] == 1
