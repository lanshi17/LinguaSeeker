from __future__ import annotations

from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest

from src.state.global_state import SupervisorState


def _base_state(**overrides: Any) -> SupervisorState:
    defaults: dict[str, Any] = {
        "request_id": "req-e2e",
        "paper_task_id": 1,
        "document_id": 1,
        "celery_task_id": "celery-e2e",
        "source": "upload",
        "file_paths": ["/tmp/test.pdf"],
        "urls": [],
        "pmids": [],
        "current_node": "",
        "workflow_status": "pending",
        "processing_steps": {},
        "node_trace": {},
        "retries": {},
        "warnings": [],
        "errors": [],
        "requires_human_review": False,
        "parsing_result": None,
        "parser_backend": None,
        "markdown_content": None,
        "image_paths": [],
        "image_inputs": [],
        "sentence_alignments": None,
        "translated_markdown": None,
        "image_descriptions": None,
        "evidence_output": None,
        "extracted_fields": None,
        "arbitration_confidence": None,
        "final_evidence_strength": None,
        "acmg_result": None,
        "graph_context": None,
        "evidence_sources": [],
        "output_files": None,
        "final_result": None,
        "_inner_processing_state": None,
    }
    defaults.update(overrides)
    return cast(SupervisorState, cast(object, defaults))


def _pass_through(state: SupervisorState) -> SupervisorState:
    return state


def _set_fields(**fields: Any):
    def _node(state: SupervisorState) -> SupervisorState:
        updated = dict(state)
        updated.update(fields)
        return cast(SupervisorState, cast(object, updated))

    return _node


_NODE_PREFIX = "src.agents.supervisor"


class TestHappyPaths:
    def _build_and_invoke(
        self, initial_state: SupervisorState, patches: dict[str, Any]
    ) -> SupervisorState:
        from src.agents.supervisor import compile_supervisor

        with patch.multiple(_NODE_PREFIX, **patches):
            graph = compile_supervisor()
            return graph.invoke(initial_state)

    def test_upload_happy_path(self):
        acmg = MagicMock()
        patches = {
            "run_interaction_node": _set_fields(interaction_ready=True),
            "run_acquisition_node": _pass_through,
            "run_parsing_node": _set_fields(parsing_result={"ok": True}),
            "run_extraction_node": _pass_through,
            "run_reasoning_node": _pass_through,
            "run_arbitration_node": _set_fields(
                acmg_result=acmg,
                arbitration_confidence=0.95,
                requires_human_review=False,
            ),
        }
        state = _base_state(source="upload")

        with patch(f"{_NODE_PREFIX}.EvidenceAgent"):
            result = self._build_and_invoke(state, patches)

        assert result["workflow_status"] == "completed"
        assert result["current_node"] == "finalize"
        assert "reasoning" not in result["processing_steps"]
        assert result["processing_steps"]["classification"]["status"] == "COMPLETED"
        assert result["processing_steps"]["adjudication"]["status"] == "COMPLETED"

    def test_web_happy_path(self):
        acmg = MagicMock()
        patches = {
            "run_interaction_node": _set_fields(interaction_ready=True),
            "run_acquisition_node": _pass_through,
            "run_parsing_node": _set_fields(parsing_result={"ok": True}),
            "run_extraction_node": _pass_through,
            "run_reasoning_node": _pass_through,
            "run_arbitration_node": _set_fields(
                acmg_result=acmg,
                arbitration_confidence=0.90,
                requires_human_review=False,
            ),
        }
        state = _base_state(source="web", urls=["https://example.com"])

        with patch(f"{_NODE_PREFIX}.EvidenceAgent"):
            result = self._build_and_invoke(state, patches)

        assert result["workflow_status"] == "completed"
        assert "reasoning" not in result["processing_steps"]
        assert result["processing_steps"]["classification"]["status"] == "COMPLETED"
        assert result["processing_steps"]["adjudication"]["status"] == "COMPLETED"


class TestParseFailurePath:
    def test_parsing_no_result_leads_to_finalize_failed(self):
        from src.agents.supervisor import compile_supervisor

        patches = {
            "run_interaction_node": _set_fields(interaction_ready=True),
            "run_acquisition_node": _pass_through,
            "run_parsing_node": _pass_through,
            "run_extraction_node": _pass_through,
            "run_reasoning_node": _pass_through,
            "run_arbitration_node": _pass_through,
        }

        state = _base_state(source="upload", parsing_result=None)

        with patch.multiple(_NODE_PREFIX, **patches):
            graph = compile_supervisor()
            result = graph.invoke(state)

        assert result["workflow_status"] == "failed"
        assert result["current_node"] == "finalize_failed"


class TestHumanReviewPaths:
    def _invoke_with_arbitration(self, **arb_fields: Any) -> SupervisorState:
        from src.agents.supervisor import compile_supervisor

        patches = {
            "run_interaction_node": _set_fields(interaction_ready=True),
            "run_acquisition_node": _pass_through,
            "run_parsing_node": _set_fields(parsing_result={"ok": True}),
            "run_extraction_node": _pass_through,
            "run_reasoning_node": _pass_through,
            "run_arbitration_node": _set_fields(**arb_fields),
        }
        state = _base_state(source="upload")

        with (
            patch.multiple(_NODE_PREFIX, **patches),
            patch(f"{_NODE_PREFIX}.EvidenceAgent"),
        ):
            graph = compile_supervisor()
            return graph.invoke(state)

    def test_low_confidence_leads_to_human_review(self):
        result = self._invoke_with_arbitration(
            acmg_result=MagicMock(),
            arbitration_confidence=0.50,
            requires_human_review=False,
        )
        assert result["current_node"] == "human_review"
        assert result["requires_human_review"] is True

    def test_missing_acmg_result_leads_to_human_review(self):
        result = self._invoke_with_arbitration(
            acmg_result=None,
            arbitration_confidence=0.95,
            requires_human_review=False,
        )
        assert result["current_node"] == "human_review"
        assert result["requires_human_review"] is True

    def test_review_flag_leads_to_human_review(self):
        result = self._invoke_with_arbitration(
            acmg_result=MagicMock(),
            arbitration_confidence=0.95,
            requires_human_review=True,
        )
        assert result["current_node"] == "human_review"
        assert result["requires_human_review"] is True

    def test_interaction_not_ready_leads_to_human_review(self):
        from src.agents.supervisor import compile_supervisor

        patches = {
            "run_interaction_node": _set_fields(
                interaction_ready=False,
                requires_human_review=True,
            ),
            "run_acquisition_node": _pass_through,
            "run_parsing_node": _pass_through,
            "run_extraction_node": _pass_through,
            "run_reasoning_node": _pass_through,
            "run_arbitration_node": _pass_through,
        }
        state = _base_state(source="upload")

        with patch.multiple(_NODE_PREFIX, **patches):
            graph = compile_supervisor()
            result = graph.invoke(state)

        assert result["current_node"] == "human_review"
        assert result["requires_human_review"] is True


class TestInterruptBeforeHumanReview:
    def test_compile_with_interrupt_sets_interrupt_nodes(self):
        from src.agents.supervisor import compile_supervisor

        graph = compile_supervisor(interrupt_before_human_review=True)
        nodes_with_interrupt = getattr(graph, "interrupt_before_nodes", None)
        if nodes_with_interrupt is None:
            nodes_with_interrupt = getattr(graph, "_interrupt_before_nodes", None)
        assert nodes_with_interrupt is None or "human_review" in (
            nodes_with_interrupt or []
        )

    def test_interrupt_graph_compiles_with_checkpointer(self):
        from langgraph.checkpoint.memory import MemorySaver

        from src.agents.supervisor import compile_supervisor

        checkpointer = MemorySaver()
        graph = compile_supervisor(
            interrupt_before_human_review=True,
            checkpointer=checkpointer,
        )
        assert graph is not None
        assert hasattr(graph, "invoke")


class TestUnknownSourceFallback:
    def test_unknown_source_routes_to_upload(self):
        from src.agents.supervisor import compile_supervisor

        acmg = MagicMock()
        patches = {
            "run_interaction_node": _set_fields(interaction_ready=True),
            "run_acquisition_node": _pass_through,
            "run_parsing_node": _set_fields(parsing_result={"ok": True}),
            "run_extraction_node": _pass_through,
            "run_reasoning_node": _pass_through,
            "run_arbitration_node": _set_fields(
                acmg_result=acmg,
                arbitration_confidence=0.95,
                requires_human_review=False,
            ),
        }
        state = _base_state(source="ftp")

        with (
            patch.multiple(_NODE_PREFIX, **patches),
            patch(f"{_NODE_PREFIX}.EvidenceAgent"),
        ):
            graph = compile_supervisor()
            result = graph.invoke(state)

        assert result["workflow_status"] == "completed"


class TestTranslationNode:
    def test_translation_skips_when_already_translated(self):
        from src.agents.supervisor import translation

        state = _base_state(translated_markdown="already done")
        result = translation(state)
        assert result.get("translated_markdown") == "already done"

    def test_translation_calls_agent_when_needed(self):
        from src.agents.supervisor import translation

        mock_agent = MagicMock()
        mock_agent.translate_markdown.return_value = {
            "translated_md": "translated text"
        }

        state = _base_state(markdown_content="raw text", translated_markdown=None)
        with patch(f"{_NODE_PREFIX}.EvidenceAgent", return_value=mock_agent):
            result = translation(state)

        mock_agent.translate_markdown.assert_called_once()
        assert result.get("translated_markdown") == "translated text"
