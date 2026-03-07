from __future__ import annotations

from typing import cast

from src.state.global_state import SupervisorState


def test_build_supervisor_graph_has_expected_nodes() -> None:
    from src.agents.supervisor import build_supervisor_graph

    graph = build_supervisor_graph()

    assert {
        "route_by_source",
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
    from src.agents.supervisor import _route_after_arbitration, _route_after_parsing

    failed_state = cast(SupervisorState, cast(object, {}))
    parsed_state = cast(SupervisorState, cast(object, {"parsing_result": {"ok": True}}))

    assert _route_after_parsing(failed_state) == "finalize_failed"
    assert _route_after_parsing(parsed_state) == "translation"
    assert (
        _route_after_arbitration(
            cast(SupervisorState, cast(object, {"requires_human_review": True}))
        )
        == "human_review"
    )
    assert (
        _route_after_arbitration(
            cast(SupervisorState, cast(object, {"requires_human_review": False}))
        )
        == "finalize"
    )


def test_compile_supervisor_returns_compiled_graph() -> None:
    from src.agents.supervisor import compile_supervisor

    compiled = compile_supervisor()

    assert compiled is not None
    assert hasattr(compiled, "invoke")
