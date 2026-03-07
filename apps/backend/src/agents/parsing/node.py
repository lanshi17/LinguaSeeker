from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from src.domain.agent.document_parsing import get_document_parsing_agent
from src.service.enum import (
    ProcessingStepStatus,
    derive_workflow_status,
    merge_processing_step_update,
    normalize_processing_steps,
)
from src.state.global_state import SupervisorState


def _string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def _node_trace_map(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    return {}


def run_parsing_node(state: SupervisorState) -> SupervisorState:
    updated: dict[str, Any] = dict(state)
    file_paths = _string_list(updated.get("file_paths"))
    if not file_paths:
        return cast(SupervisorState, cast(object, updated))

    result = get_document_parsing_agent().parse_documents(file_paths)
    updated["current_node"] = "parsing"
    updated["parsing_result"] = result.model_dump(mode="json")
    updated["parser_backend"] = result.parser_backend
    updated["markdown_content"] = result.markdown_content
    updated["image_paths"] = list(result.image_paths)

    node_trace = _node_trace_map(updated.get("node_trace"))
    node_trace["parsing"] = "success"
    updated["node_trace"] = node_trace

    processing_steps = normalize_processing_steps(
        updated.get("processing_steps"),
        node_trace=node_trace,
    )
    processing_steps = merge_processing_step_update(
        processing_steps,
        step="parsing",
        status=ProcessingStepStatus.completed,
        message="Parsing completed",
    )
    updated["processing_steps"] = processing_steps
    updated["workflow_status"] = derive_workflow_status(processing_steps).value

    return cast(SupervisorState, cast(object, updated))


__all__ = ["run_parsing_node"]
