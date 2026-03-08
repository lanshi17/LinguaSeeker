from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from langgraph.graph import END, START, StateGraph

from src.agents.acquisition import run_acquisition_node
from src.agents.arbitration import run_arbitration_node
from src.agents.extraction import run_extraction_node
from src.agents.interaction import run_interaction_node
from src.agents.parsing import run_parsing_node
from src.domain.agent.workflow import EvidenceAgent
from src.domain.enums import ProcessingState
from src.state.global_state import SupervisorState


def _dict_value(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    return {}


def _string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str) and value:
        return [value]
    return []


def _to_float(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip().rstrip("%")
        if not stripped:
            return None
        try:
            return float(stripped)
        except ValueError:
            return None
    return None


def _is_low_confidence(value: object) -> bool:
    confidence = _to_float(value)
    if confidence is None:
        return False
    threshold = 0.85 if confidence <= 1.0 else 85.0
    return confidence < threshold


def route_by_source(state: SupervisorState) -> SupervisorState:
    updated = dict(state)
    updated["current_node"] = "route_by_source"
    return cast(SupervisorState, cast(object, updated))


def _route_by_source(state: SupervisorState) -> str:
    source = str(state.get("source", "upload")).strip().lower()
    if source in {"upload", "pubmed", "web"}:
        return source
    return "upload"


def translation(state: SupervisorState) -> SupervisorState:
    updated: dict[str, Any] = dict(state)
    updated["current_node"] = "translation"
    if updated.get("translated_markdown"):
        return cast(SupervisorState, cast(object, updated))

    agent = EvidenceAgent()
    inner_state = _dict_value(updated.get("_inner_processing_state"))
    inner_state.update(
        {
            "markdown_content": updated.get("markdown_content", "") or "",
            "translated_md": updated.get("translated_markdown", "") or "",
            "image_paths": _string_list(updated.get("image_paths")),
            "image_descriptions": _string_list(updated.get("image_descriptions")),
            "status": updated.get("workflow_status", "pending") or "pending",
        }
    )
    final_state = agent.translate_markdown(cast(ProcessingState, cast(object, inner_state)))
    updated["_inner_processing_state"] = final_state
    updated["translated_markdown"] = final_state.get("translated_md") or updated.get(
        "markdown_content", ""
    )
    return cast(SupervisorState, cast(object, updated))


def finalize(state: SupervisorState) -> SupervisorState:
    updated = dict(state)
    updated["current_node"] = "finalize"
    updated["workflow_status"] = "completed"
    return cast(SupervisorState, cast(object, updated))


def finalize_failed(state: SupervisorState) -> SupervisorState:
    updated = dict(state)
    updated["current_node"] = "finalize_failed"
    updated["workflow_status"] = "failed"
    return cast(SupervisorState, cast(object, updated))


def human_review(state: SupervisorState) -> SupervisorState:
    updated = dict(state)
    updated["current_node"] = "human_review"
    updated["requires_human_review"] = True
    return cast(SupervisorState, cast(object, updated))


def _route_after_parsing(state: SupervisorState) -> str:
    return "translation" if state.get("parsing_result") else "finalize_failed"


def _route_after_interaction(state: SupervisorState) -> str:
    interaction_ready = state.get("interaction_ready")
    if interaction_ready is False or state.get("requires_human_review"):
        return "human_review"
    return "acquisition"


def _route_after_arbitration(state: SupervisorState) -> str:
    if state.get("requires_human_review"):
        return "human_review"
    if not state.get("acmg_result"):
        return "human_review"
    if _is_low_confidence(state.get("arbitration_confidence")):
        return "human_review"
    return "finalize"


def build_supervisor_graph() -> StateGraph[SupervisorState]:
    graph = StateGraph(SupervisorState)
    graph.add_node("route_by_source", route_by_source)
    graph.add_node("interaction", run_interaction_node)
    graph.add_node("acquisition", run_acquisition_node)
    graph.add_node("parsing", run_parsing_node)
    graph.add_node("translation", translation)
    graph.add_node("extraction", run_extraction_node)
    graph.add_node("arbitration", run_arbitration_node)
    graph.add_node("finalize", finalize)
    graph.add_node("finalize_failed", finalize_failed)
    graph.add_node("human_review", human_review)

    graph.add_edge(START, "route_by_source")
    graph.add_conditional_edges(
        "route_by_source",
        _route_by_source,
        {"upload": "interaction", "pubmed": "interaction", "web": "interaction"},
    )
    graph.add_conditional_edges(
        "interaction",
        _route_after_interaction,
        {"acquisition": "acquisition", "human_review": "human_review"},
    )
    graph.add_edge("acquisition", "parsing")
    graph.add_conditional_edges(
        "parsing",
        _route_after_parsing,
        {"translation": "translation", "finalize_failed": "finalize_failed"},
    )
    graph.add_edge("translation", "extraction")
    graph.add_edge("extraction", "arbitration")
    graph.add_conditional_edges(
        "arbitration",
        _route_after_arbitration,
        {"finalize": "finalize", "human_review": "human_review"},
    )
    graph.add_edge("finalize", END)
    graph.add_edge("finalize_failed", END)
    graph.add_edge("human_review", END)
    return graph


def compile_supervisor(
    *,
    interrupt_before_human_review: bool = False,
    checkpointer: Any | None = None,
):
    interrupt_before_nodes = ["human_review"] if interrupt_before_human_review else None
    return build_supervisor_graph().compile(
        checkpointer=checkpointer,
        interrupt_before=interrupt_before_nodes,
    )


__all__ = [
    "_route_after_arbitration",
    "_route_after_interaction",
    "_route_after_parsing",
    "build_supervisor_graph",
    "compile_supervisor",
]
