from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from src.agents.arbitration.ps3_bs3_evaluator import EvidenceClassifier
from src.domain.agent.workflow import EvidenceAgent
from src.domain.enums import ProcessingState
from src.domain.models import EvidenceOutput, ExtractedEvidenceFields
from src.state.global_state import SupervisorState


def _string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str) and value:
        return [value]
    return []


def _dict_value(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    return {}


def _structured_fields_value(value: object) -> dict[str, Any]:
    if isinstance(value, ExtractedEvidenceFields):
        return value.model_dump(mode="json")
    return _dict_value(value)


def run_arbitration_node(state: SupervisorState) -> SupervisorState:
    updated: dict[str, Any] = dict(state)
    existing_output = updated.get("evidence_output")
    ps3_evidence = (
        existing_output.ps3_evidence if isinstance(existing_output, EvidenceOutput) else {}
    )
    inner_state = _dict_value(updated.get("_inner_processing_state"))
    inner_state.update(
        {
            "markdown_content": updated.get("markdown_content", "") or "",
            "translated_md": updated.get("translated_markdown", "") or "",
            "image_paths": _string_list(updated.get("image_paths")),
            "image_descriptions": _string_list(updated.get("image_descriptions")),
            "ps3_evidence": ps3_evidence,
            "extracted_fields": _structured_fields_value(updated.get("extracted_fields")),
            "arbitration_confidence": updated.get("arbitration_confidence"),
            "graph_context": updated.get("graph_context"),
            "status": updated.get("workflow_status", "pending") or "pending",
        }
    )

    agent = EvidenceAgent()
    final_state = agent.arbitrate_score(cast(ProcessingState, cast(object, inner_state)))
    decision = agent.route_decision(final_state)
    final_strength = _dict_value(
        _dict_value(final_state.get("ps3_evidence")).get("ps3_step_4")
    ).get("final_evidence_strength")
    acmg_result = EvidenceClassifier.classify(
        _dict_value(final_state.get("ps3_evidence")),
        extracted_fields=_structured_fields_value(updated.get("extracted_fields")),
    )

    updated["current_node"] = "arbitrate"
    updated["_inner_processing_state"] = final_state
    updated["arbitration_confidence"] = final_state.get("arbitration_confidence")
    updated["final_evidence_strength"] = final_strength
    updated["acmg_result"] = acmg_result
    updated["requires_human_review"] = decision != "approved"

    if isinstance(existing_output, EvidenceOutput):
        updated["evidence_output"] = existing_output.model_copy(
            update={
                "ps3_evidence": _dict_value(final_state.get("ps3_evidence")),
                "arbitration_confidence": final_state.get("arbitration_confidence"),
                "final_evidence_strength": final_strength,
            }
        )

    return cast(SupervisorState, cast(object, updated))


__all__ = ["run_arbitration_node"]
