from __future__ import annotations

from typing import cast

from src.state.global_state import SupervisorState


def test_build_supervisor_graph_has_expected_nodes() -> None:
    from src.agents.supervisor import build_supervisor_graph

    graph = build_supervisor_graph()

    assert {
        "route_by_source",
        "interaction",
        "acquisition",
        "parsing",
        "translation",
        "extraction",
        "arbitration",
        "finalize",
        "finalize_failed",
        "human_review",
    } <= set(graph.nodes)


def test_routing_parsing_failed() -> None:
    from src.agents.supervisor import (
        _route_after_arbitration,
        _route_after_interaction,
        _route_after_parsing,
    )

    failed_state = cast(SupervisorState, cast(object, {}))
    parsed_state = cast(SupervisorState, cast(object, {"parsing_result": {"ok": True}}))

    assert _route_after_parsing(failed_state) == "finalize_failed"
    assert _route_after_parsing(parsed_state) == "translation"
    assert _route_after_interaction(failed_state) == "acquisition"
    assert (
        _route_after_interaction(
            cast(
                SupervisorState,
                cast(
                    object,
                    {
                        "interaction_ready": False,
                        "requires_human_review": True,
                        "question": "Need clarification",
                    },
                ),
            )
        )
        == "human_review"
    )


def test_routing_after_arbitration_respects_review_rules() -> None:
    from src.agents.supervisor import _route_after_arbitration

    assert (
        _route_after_arbitration(
            cast(SupervisorState, cast(object, {"requires_human_review": True}))
        )
        == "human_review"
    )
    assert (
        _route_after_arbitration(
            cast(
                SupervisorState,
                cast(
                    object,
                    {
                        "requires_human_review": False,
                        "acmg_result": {"classification": "Pathogenic"},
                        "arbitration_confidence": 0.95,
                    },
                ),
            )
        )
        == "finalize"
    )
    assert (
        _route_after_arbitration(
            cast(
                SupervisorState,
                cast(
                    object,
                    {
                        "requires_human_review": False,
                        "acmg_result": None,
                        "arbitration_confidence": 0.95,
                    },
                ),
            )
        )
        == "human_review"
    )
    assert (
        _route_after_arbitration(
            cast(
                SupervisorState,
                cast(
                    object,
                    {
                        "requires_human_review": False,
                        "acmg_result": {"classification": "Pathogenic"},
                        "arbitration_confidence": 0.75,
                    },
                ),
            )
        )
        == "human_review"
    )
    assert (
        _route_after_arbitration(
            cast(
                SupervisorState,
                cast(
                    object,
                    {
                        "requires_human_review": False,
                        "acmg_result": {"classification": "Pathogenic"},
                        "arbitration_confidence": 75.0,
                    },
                ),
            )
        )
        == "human_review"
    )
    assert (
        _route_after_arbitration(
            cast(
                SupervisorState,
                cast(
                    object,
                    {
                        "requires_human_review": False,
                        "acmg_result": {"classification": "Pathogenic"},
                        "arbitration_confidence": 0.95,
                    },
                ),
            )
        )
        == "finalize"
    )


def test_compile_supervisor_returns_compiled_graph() -> None:
    from src.agents.supervisor import compile_supervisor

    compiled = compile_supervisor()

    assert compiled is not None
    assert hasattr(compiled, "invoke")


def test_compile_supervisor_can_interrupt_before_human_review() -> None:
    from src.agents.supervisor import compile_supervisor

    compiled = compile_supervisor(interrupt_before_human_review=True)

    assert compiled.interrupt_before_nodes == ["human_review"]
