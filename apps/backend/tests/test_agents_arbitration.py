from __future__ import annotations

from typing import Any, cast

from src.domain.evidence.classifier import (
    EvidenceClassifier as LegacyEvidenceClassifier,
)
from src.domain.evidence.evaluation_framework import (
    calculate_oddpath as legacy_calculate_oddpath,
)
from src.domain.evidence.evaluation_framework import (
    determine_evidence_strength as legacy_determine_evidence_strength,
)
from src.domain.models import EvidenceOutput, EvidenceStrengthClassification
from src.state.global_state import SupervisorState


def test_arbitration_reexports_are_identity() -> None:
    from src.agents.arbitration import (
        EvidenceClassifier,
        calculate_oddpath,
        determine_evidence_strength,
        run_arbitration_node,
    )

    assert EvidenceClassifier is LegacyEvidenceClassifier
    assert calculate_oddpath is legacy_calculate_oddpath
    assert determine_evidence_strength is legacy_determine_evidence_strength
    assert callable(run_arbitration_node)


def test_run_arbitration_node_maps_processing_state(monkeypatch) -> None:
    from src.agents.arbitration import node as arbitration_node

    class FakeEvidenceAgent:
        def arbitrate_score(self, inner_state: dict[str, Any]) -> dict[str, Any]:
            inner_state["arbitration_confidence"] = 0.91
            inner_state["arbitration_score"] = 91.0
            inner_state["ps3_evidence"] = {
                "ps3_step_4": {"final_evidence_strength": "PS3"},
                "overall_assessment": {"final_recommendation": "PS3"},
            }
            return inner_state

        def route_decision(self, inner_state: dict[str, Any]) -> str:
            assert inner_state["arbitration_score"] == 91.0
            return "approved"

    monkeypatch.setattr(arbitration_node, "EvidenceAgent", FakeEvidenceAgent)
    monkeypatch.setattr(
        arbitration_node.EvidenceClassifier,
        "classify",
        staticmethod(
            lambda ps3_evidence, extracted_fields=None: EvidenceStrengthClassification(
                overall_score=91.0,
                classification="Pathogenic",
                acmg_levels=["PS3"],
                is_valid=True,
                validity_reason="meets_threshold",
                reasoning=None,
            )
        ),
    )

    state = cast(
        SupervisorState,
        cast(
            object,
            {
                "markdown_content": "# original",
                "translated_markdown": "# translated",
                "image_descriptions": ["figure"],
                "evidence_output": EvidenceOutput(
                    ps3_evidence={
                        "ps3_step_4": {"final_evidence_strength": "PS3"},
                        "overall_assessment": {"final_recommendation": "PS3"},
                    },
                    arbitration_confidence=None,
                    image_descriptions=[],
                    final_evidence_strength=None,
                    status="pending",
                    origin_format_md="",
                    en_format_md="",
                    extracted_fields=None,
                    field_confidence_scores=None,
                    overall_confidence=None,
                    evidence_classification=None,
                    acmg_evidence_levels=None,
                ),
                "extracted_fields": {"gene": {"symbol": "BRCA1", "confidence": 91.0}},
            },
        ),
    )

    result = arbitration_node.run_arbitration_node(state)

    assert result["current_node"] == "arbitration"
    assert result["arbitration_confidence"] == 0.91
    assert result["final_evidence_strength"] == "PS3"
    assert result["requires_human_review"] is False
    assert isinstance(result["acmg_result"], EvidenceStrengthClassification)
    assert result["acmg_result"].overall_score == 91.0
