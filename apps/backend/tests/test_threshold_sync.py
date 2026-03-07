from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from src.domain.enums import ODDSPATH_STRENGTH_MAP, SCORE_CLASSIFICATION_MAP
from src.domain.agent import prompts
from src.domain.evidence.classifier import EvidenceClassifier
from src.domain.evidence.evaluation_framework import determine_strength_by_oddpath


def _json_value(value: Any) -> Any:
    return getattr(value, "value", value)


class TestArbitrationThresholds:
    def test_score_threshold(self) -> None:
        from src.domain.agent.prompts import ARBITRATION_SCORE_THRESHOLD

        assert ARBITRATION_SCORE_THRESHOLD == 85.0

    def test_confidence_threshold(self) -> None:
        from src.domain.agent.prompts import ARBITRATION_CONFIDENCE_THRESHOLD

        assert ARBITRATION_CONFIDENCE_THRESHOLD == 0.85

    def test_prompt_embedded_oddspath_thresholds(self) -> None:
        assert prompts.ODDSPATH_THRESHOLDS == {
            "BS3_very_strong": 0.0029,
            "BS3": 0.053,
            "BS3_moderate": 0.23,
            "BS3_supporting": 1.0,
            "PS3_supporting": 4.3,
            "PS3_moderate": 18.7,
            "PS3": 350,
            "PS3_very_strong": 350,
        }

        prompt_source = (
            (Path(prompts.__file__).read_text())
            + (
                Path(__file__).resolve().parents[1] / "src/knowledge/prompts/arbitration.yaml"
            ).read_text()
            + (
                Path(__file__).resolve().parents[1] / "src/knowledge/prompts/acmg_rules.yaml"
            ).read_text()
        )
        for fragment in [
            "PS3 supporting when OddsPath > 1.0 and <= 4.3",
            "BS3 very strong when < 0.0029",
            "| < 0.0029       | BS3_very_strong  |",
            "| 0.23 - 1.0     | BS3_supporting   |",
            "| 18.7 - 350     | PS3              |",
            '"BS3_very_strong": 0.0029',
            '"PS3_supporting": 4.3',
            '"PS3": 350',
        ]:
            assert fragment in prompt_source


class TestOddsPathBreakpoints:
    @pytest.mark.parametrize(
        ("odds_path", "expected_strength"),
        [
            (-0.1, "inconclusive"),
            (0.0, "BS3_very_strong"),
            (0.0028, "BS3_very_strong"),
            (0.0029, "BS3"),
            (0.0529, "BS3"),
            (0.053, "BS3_moderate"),
            (0.2299, "BS3_moderate"),
            (0.23, "BS3_supporting"),
            (1.0, "BS3_supporting"),
            (1.0001, "PS3_supporting"),
            (4.3, "PS3_supporting"),
            (4.3001, "PS3_moderate"),
            (18.7, "PS3_moderate"),
            (18.7001, "PS3"),
            (350.0, "PS3"),
            (350.1, "PS3_very_strong"),
        ],
    )
    def test_classifier_breakpoints(self, odds_path: float, expected_strength: str) -> None:
        result = EvidenceClassifier.oddspath_to_strength(odds_path)
        assert _json_value(result) == expected_strength

    @pytest.mark.parametrize(
        ("odds_path", "expected_strength"),
        [
            (-0.1, "Supporting"),
            (0.0, "Very Strong"),
            (0.0028, "Very Strong"),
            (0.0029, "Strong"),
            (0.0529, "Strong"),
            (0.053, "Moderate"),
            (0.2299, "Moderate"),
            (0.23, "Supporting"),
            (1.0, "Supporting"),
            (1.0001, "Supporting"),
            (4.3, "Supporting"),
            (4.3001, "Moderate"),
            (18.7, "Moderate"),
            (18.7001, "Strong"),
            (350.0, "Strong"),
            (350.1, "Very Strong"),
        ],
    )
    def test_evaluation_framework_breakpoints(
        self, odds_path: float, expected_strength: str
    ) -> None:
        assert determine_strength_by_oddpath(odds_path) == expected_strength

    @pytest.mark.parametrize(
        "odds_path",
        [0.001, 0.01, 0.1, 0.5, 2.0, 10.0, 100.0, 500.0],
    )
    def test_breakpoints_cross_module_consistency(self, odds_path: float) -> None:
        generic_strength = determine_strength_by_oddpath(odds_path)
        direction = "benign" if odds_path < 1 else "pathogenic"
        mapped_strength = {
            "Supporting": {
                "benign": "BS3_supporting",
                "pathogenic": "PS3_supporting",
            },
            "Moderate": {
                "benign": "BS3_moderate",
                "pathogenic": "PS3_moderate",
            },
            "Strong": {
                "benign": "BS3",
                "pathogenic": "PS3",
            },
            "Very Strong": {
                "benign": "BS3_very_strong",
                "pathogenic": "PS3_very_strong",
            },
        }[generic_strength][direction]

        assert _json_value(EvidenceClassifier.oddspath_to_strength(odds_path)) == mapped_strength


class TestClassifierWeighting:
    def test_overall_score_formula(self) -> None:
        ps3_evidence = {
            "overall_assessment": {"total_score": 80.0},
            "ps3_step_4": {"final_evidence_strength": "PS3"},
        }
        extracted_fields = {
            "gene": {
                "symbol": "BRCA1",
                "confidence": 50.0,
            }
        }

        result = EvidenceClassifier.classify(ps3_evidence, extracted_fields=extracted_fields)

        assert result.overall_score == pytest.approx(68.0)
        assert _json_value(result.classification) == "Likely Pathogenic"
        assert [_json_value(level) for level in result.acmg_levels] == ["PS3"]


class TestScoreClassificationMap:
    def test_score_classification_map_values(self) -> None:
        assert [
            (threshold, _json_value(classification))
            for threshold, classification in SCORE_CLASSIFICATION_MAP
        ] == [
            (85.0, "Pathogenic"),
            (80.0, "Strong Pathogenic"),
            (70.0, "Moderate Pathogenic"),
            (60.0, "Likely Pathogenic"),
            (40.0, "Uncertain Significance"),
            (20.0, "Likely Benign"),
            (0.0, "Benign"),
        ]


class TestOddsPathStrengthMap:
    def test_oddspath_strength_map_values(self) -> None:
        assert [
            (threshold, _json_value(strength)) for threshold, strength in ODDSPATH_STRENGTH_MAP
        ] == [
            (350.0, "PS3_very_strong"),
            (18.7, "PS3"),
            (4.3, "PS3_moderate"),
            (1.0, "PS3_supporting"),
            (0.23, "BS3_supporting"),
            (0.053, "BS3_moderate"),
            (0.0029, "BS3"),
        ]
