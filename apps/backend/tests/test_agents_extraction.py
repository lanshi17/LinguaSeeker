from __future__ import annotations

from typing import Any, cast

from src.domain.evidence.tools import EVIDENCE_TOOLS as LEGACY_EVIDENCE_TOOLS
from src.domain.evidence.tools import get_evidence_tool_map as legacy_get_evidence_tool_map
from src.domain.evidence.tools import get_evidence_tools as legacy_get_evidence_tools
from src.domain.models import EvidenceOutput, ExtractedEvidenceFields, GeneInfo
from src.state.global_state import SupervisorState


def test_extraction_tool_reexports_are_identity() -> None:
    from src.agents.extraction import (
        EVIDENCE_TOOLS,
        get_evidence_tool_map,
        get_evidence_tools,
        run_extraction_node,
    )

    assert EVIDENCE_TOOLS is LEGACY_EVIDENCE_TOOLS
    assert get_evidence_tools is legacy_get_evidence_tools
    assert get_evidence_tool_map is legacy_get_evidence_tool_map
    assert callable(run_extraction_node)


def test_run_extraction_node_maps_processing_state(monkeypatch) -> None:
    from src.agents.extraction import node as extraction_node

    class FakeEvidenceAgent:
        def extract_ps3_evidence_sync(self, inner_state: dict[str, Any]) -> dict[str, Any]:
            assert inner_state["translated_md"] == "# translated"
            assert inner_state["image_descriptions"] == ["figure"]
            inner_state["ps3_evidence"] = {
                "ps3_step_4": {"final_evidence_strength": "PS3"},
                "overall_assessment": {"final_recommendation": "PS3"},
            }
            inner_state["evidence_sources"] = ["Figure 1"]
            return inner_state

        def _extract_output_contract_fields(
            self, state: dict[str, Any], final_strength: str | None
        ) -> dict[str, Any]:
            assert final_strength == "PS3"
            return {
                "extracted_fields": {"gene": {"symbol": "BRCA1", "confidence": 91.0}},
                "field_confidence_scores": {"gene": 91.0},
                "overall_confidence": 91.0,
                "evidence_classification": "Pathogenic",
                "acmg_evidence_levels": ["PS3"],
            }

    monkeypatch.setattr(extraction_node, "EvidenceAgent", FakeEvidenceAgent)

    state = cast(
        SupervisorState,
        cast(
            object,
            {
                "markdown_content": "# original",
                "translated_markdown": "# translated",
                "image_descriptions": ["figure"],
            },
        ),
    )

    result = extraction_node.run_extraction_node(state)
    result_dict = cast(dict[str, Any], cast(object, result))

    assert isinstance(result["evidence_output"], EvidenceOutput)
    assert result["evidence_output"].final_evidence_strength == "PS3"
    assert result_dict["overall_confidence"] == 91.0
    assert result_dict["field_confidence_scores"] == {"gene": 91.0}
    assert isinstance(result["extracted_fields"], ExtractedEvidenceFields)
    assert result["extracted_fields"].gene == GeneInfo(
        symbol="BRCA1",
        full_name=None,
        ncbi_gene_id=None,
        ensembl_id=None,
        evidence_quote=None,
        confidence=91.0,
    )
    assert result["evidence_sources"] == ["Figure 1"]
