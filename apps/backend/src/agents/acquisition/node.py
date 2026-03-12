from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

from src.domain.literature.acquisition_agent import get_literature_acquisition_agent
from src.services.enum import (
    ProcessingStepStatus,
    derive_workflow_status,
    merge_processing_step_update,
    normalize_processing_steps,
)
from src.state.global_state import SupervisorState
from src.utils.exceptions import ValidationException


def _string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def _node_trace_map(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    return {}


def _mark_acquisition_success(updated: dict[str, Any], message: str) -> None:
    node_trace = _node_trace_map(updated.get("node_trace"))
    node_trace["acquisition"] = "success"
    updated["node_trace"] = node_trace

    processing_steps = normalize_processing_steps(
        updated.get("processing_steps"),
        node_trace=node_trace,
    )
    processing_steps = merge_processing_step_update(
        processing_steps,
        step="acquisition",
        status=ProcessingStepStatus.completed,
        message=message,
    )
    updated["processing_steps"] = processing_steps
    updated["workflow_status"] = derive_workflow_status(processing_steps).value


def run_acquisition_node(state: SupervisorState) -> SupervisorState:
    updated: dict[str, Any] = dict(state)
    source = str(updated.get("source", "")).strip().lower()
    updated["current_node"] = "acquisition"

    if source == "upload":
        file_paths = _string_list(updated.get("file_paths"))
        missing = [path for path in file_paths if not Path(path).is_file()]
        if missing:
            raise ValidationException(f"Files not found: {', '.join(missing)}")
        _mark_acquisition_success(updated, "Acquisition completed")
        return cast(SupervisorState, cast(object, updated))

    agent = get_literature_acquisition_agent()
    if source == "pubmed":
        pmids = _string_list(updated.get("pmids"))
        plan_items = agent.plan_pubmed_request(pmids)
        updated["pmids"] = [item.normalized_value for item in plan_items]
    elif source == "web":
        urls = _string_list(updated.get("urls"))
        plan_items = agent.plan_web_request(urls)
        updated["urls"] = [item.normalized_value for item in plan_items]
    else:
        raise ValidationException(f"Unsupported acquisition source: {source}")

    updated["acquisition_plan"] = [asdict(item) for item in plan_items]
    _mark_acquisition_success(updated, "Acquisition completed")
    return cast(SupervisorState, cast(object, updated))


__all__ = ["run_acquisition_node"]
