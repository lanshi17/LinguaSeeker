from __future__ import annotations

from typing import cast

from src.domain.agent.interaction import InteractionAgent as LegacyInteractionAgent
from src.domain.agent.interaction import TaskFormStructured as LegacyTaskFormStructured
from src.state.global_state import SupervisorState


def test_interaction_wrapper_imports_and_legacy_compatibility() -> None:
    from src.agents.interaction import (
        INTERACTION_SYSTEM_PROMPT,
        InteractionAgent,
        TaskFormStructured,
        run_interaction_node,
    )

    assert InteractionAgent is LegacyInteractionAgent
    assert TaskFormStructured is LegacyTaskFormStructured
    assert callable(run_interaction_node)
    assert "genetics literature search assistant" in INTERACTION_SYSTEM_PROMPT


def test_run_interaction_node_smoke_passthrough() -> None:
    from src.agents.interaction import run_interaction_node

    state = cast(SupervisorState, cast(object, {}))

    assert run_interaction_node(state) == state


def test_run_interaction_node_maps_start_result(monkeypatch) -> None:
    from src.agents.interaction import node as interaction_node

    class FakeInteractionAgent:
        async def start_interaction(self, user_input: str) -> dict[str, object]:
            assert user_input == "find functional evidence"
            return {
                "session_id": "session-1",
                "ready": True,
                "task_form": {
                    "goal": "functional evidence",
                    "disease": "LDLR",
                    "country": "不限",
                    "language": "auto",
                },
                "question": None,
                "round": 0,
            }

    monkeypatch.setattr(interaction_node, "InteractionAgent", FakeInteractionAgent)

    result = interaction_node.run_interaction_node(
        cast(SupervisorState, cast(object, {"user_input": "find functional evidence"}))
    )
    result_dict = cast(dict[str, object], cast(object, result))

    assert result["current_node"] == "interaction"
    assert result_dict["session_id"] == "session-1"
    assert result["requires_human_review"] is False
    assert result_dict["goal"] == "functional evidence"
    assert result_dict["disease"] == "LDLR"
    assert result_dict["country"] == "不限"
    assert result_dict["language"] == "auto"
