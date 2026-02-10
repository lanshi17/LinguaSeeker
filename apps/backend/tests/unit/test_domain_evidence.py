from types import SimpleNamespace

import pytest

from src.domain.evidence import aggregator as aggregator_module
from src.domain.evidence import classifier as classifier_module
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


def test_determine_evidence_strength_from_oddspath() -> None:
    assert tools_module.determine_evidence_strength_from_oddspath(0.02) == "BS3"
    assert tools_module.determine_evidence_strength_from_oddspath(0.1) == "BS3_moderate"
    assert tools_module.determine_evidence_strength_from_oddspath(0.3) == "BS3_supporting"
    assert tools_module.determine_evidence_strength_from_oddspath(1.0) == "inconclusive"
    assert tools_module.determine_evidence_strength_from_oddspath(3.0) == "PS3_supporting"
    assert tools_module.determine_evidence_strength_from_oddspath(5.0) == "PS3_moderate"
    assert tools_module.determine_evidence_strength_from_oddspath(20.0) == "PS3"
    assert tools_module.determine_evidence_strength_from_oddspath(400.0) == "PS3_very_strong"


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
    assert classifier_module.EvidenceClassifier.max_strength_from_controls(0) == "none"
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
