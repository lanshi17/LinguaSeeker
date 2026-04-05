from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from src.services.enum import (
    PROCESSING_NODE_TO_STEP,
    PROCESSING_STEP_ORDER,
    normalize_processing_steps,
)


def normalize_warning_codes(value: Any) -> Optional[List[str]]:
    if value is None:
        return None
    if isinstance(value, str):
        codes = [value]
    elif isinstance(value, (list, tuple, set)):
        codes = [str(item).strip() for item in value if str(item).strip()]
    else:
        text = str(value).strip()
        codes = [text] if text else []
    deduped = list(dict.fromkeys(codes))
    return deduped or None


def _step_outcome(node_trace: Mapping[str, Any], step: str) -> Optional[str]:
    preferred_keys: Dict[str, List[str]] = {
        "classification": ["classification", "acmg"],
        "adjudication": ["adjudication", "arbitration", "human_review"],
    }
    for candidate in preferred_keys.get(step, [step]):
        value = node_trace.get(candidate)
        if value is not None and not isinstance(value, Mapping):
            return str(value)

    for raw_key, raw_value in node_trace.items():
        if isinstance(raw_value, Mapping):
            continue
        if PROCESSING_NODE_TO_STEP.get(str(raw_key).lower()) == step:
            return str(raw_value)
    return None


def build_trace_chain(
    *,
    node_trace: Optional[Mapping[str, Any]],
    processing_steps: Any,
) -> Optional[Dict[str, Any]]:
    normalized_steps = normalize_processing_steps(
        processing_steps,
        node_trace=node_trace,
    )
    if not normalized_steps and not node_trace:
        return None

    trace_steps: Dict[str, Dict[str, Any]] = {}
    for step in PROCESSING_STEP_ORDER:
        step_state = normalized_steps.get(step, {})
        entry: Dict[str, Any] = {"status": step_state.get("status")}
        outcome = _step_outcome(node_trace or {}, step)
        if outcome:
            entry["outcome"] = outcome
        message = step_state.get("message")
        if message:
            entry["message"] = message
        error_code = step_state.get("error_code")
        if error_code:
            entry["error_code"] = error_code
        if step == "acquisition" and isinstance(
            (node_trace or {}).get("acquisition_detail"), Mapping
        ):
            entry["detail"] = dict((node_trace or {})["acquisition_detail"])
        trace_steps[step] = entry

    return {"steps": trace_steps}
