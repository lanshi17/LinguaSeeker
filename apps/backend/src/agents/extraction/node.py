from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

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


def run_extraction_node(state: SupervisorState) -> SupervisorState:
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
            "evidence_sources": _string_list(updated.get("evidence_sources")),
            "field_confidence_scores": _dict_value(updated.get("field_confidence_scores")),
            "overall_confidence": updated.get("overall_confidence", 0.0) or 0.0,
            "status": updated.get("workflow_status", "pending") or "pending",
        }
    )

    agent = EvidenceAgent()
    final_state = agent.extract_ps3_evidence_sync(cast(ProcessingState, cast(object, inner_state)))
    final_strength = _dict_value(
        _dict_value(final_state.get("ps3_evidence")).get("ps3_step_4")
    ).get("final_evidence_strength")
    contract_fields = agent._extract_output_contract_fields(final_state, final_strength)
    extracted_fields_raw = _dict_value(contract_fields.get("extracted_fields"))
    extracted_fields = (
        ExtractedEvidenceFields.model_validate(extracted_fields_raw)
        if extracted_fields_raw
        else None
    )
    evidence_output = EvidenceOutput(
        ps3_evidence=_dict_value(final_state.get("ps3_evidence")),
        arbitration_confidence=final_state.get("arbitration_confidence"),
        image_descriptions=_string_list(final_state.get("image_descriptions")),
        final_evidence_strength=cast(str | None, final_strength),
        status=str(final_state.get("status", "pending")),
        origin_format_md=str(final_state.get("markdown_content", "")),
        en_format_md=str(final_state.get("translated_md", "")),
        extracted_fields=extracted_fields_raw or None,
        field_confidence_scores=cast(
            dict[str, float] | None, contract_fields.get("field_confidence_scores")
        ),
        overall_confidence=cast(float | None, contract_fields.get("overall_confidence")),
        evidence_classification=cast(str | None, contract_fields.get("evidence_classification")),
        acmg_evidence_levels=cast(list[str] | None, contract_fields.get("acmg_evidence_levels")),
    )

    updated["current_node"] = "extract_evidence"
    updated["_inner_processing_state"] = final_state
    updated["evidence_output"] = evidence_output
    updated["extracted_fields"] = extracted_fields
    updated["evidence_sources"] = _string_list(final_state.get("evidence_sources"))
    updated["field_confidence_scores"] = contract_fields.get("field_confidence_scores")
    updated["overall_confidence"] = contract_fields.get("overall_confidence")

    return cast(SupervisorState, cast(object, updated))


__all__ = ["run_extraction_node"]
