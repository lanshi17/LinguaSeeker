from __future__ import annotations

import asyncio
from typing import Any, cast

from src.domain.agent.interaction import InteractionAgent
from src.state.global_state import SupervisorState


def run_interaction_node(state: SupervisorState) -> SupervisorState:
    updated = dict(state)
    user_input = updated.get("user_input")
    session_id = updated.get("session_id")
    user_response = updated.get("user_response")

    if not user_input and not (session_id and user_response):
        return cast(SupervisorState, cast(object, updated))

    agent = InteractionAgent()
    if session_id and user_response:
        result = asyncio.run(agent.respond_interaction(str(session_id), str(user_response)))
    else:
        result = asyncio.run(agent.start_interaction(str(user_input)))

    updated["current_node"] = "interaction"
    updated["session_id"] = result.get("session_id")
    updated["question"] = result.get("question")
    updated["task_form"] = result.get("task_form")
    updated["interaction_ready"] = result.get("ready")
    updated["requires_human_review"] = not bool(result.get("ready"))
    if isinstance(result.get("task_form"), dict):
        task_form = cast(dict[str, Any], result["task_form"])
        updated["goal"] = task_form.get("goal")
        updated["disease"] = task_form.get("disease")
        updated["country"] = task_form.get("country")
        updated["language"] = task_form.get("language")

    return cast(SupervisorState, cast(object, updated))


__all__ = ["run_interaction_node"]
