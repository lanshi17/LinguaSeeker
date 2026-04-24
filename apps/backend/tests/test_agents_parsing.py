from __future__ import annotations

from typing import Any, cast

from langchain_core.messages import AIMessage

from src.domain.agent.document_parsing import DocumentParsingAgent as LegacyDocumentParsingAgent
from src.domain.agent.workflow import EvidenceAgent
from src.domain.mineru.component import MinerUComponent as LegacyMinerUComponent
from src.domain.models import DocumentParsingResult
from src.services.enum import default_processing_steps
from src.state.global_state import SupervisorState


def test_parsing_wrapper_imports_and_legacy_compatibility() -> None:
    from src.agents.parsing import DocumentParsingAgent, MinerUComponent, run_parsing_node

    assert DocumentParsingAgent is LegacyDocumentParsingAgent
    assert MinerUComponent is LegacyMinerUComponent
    assert callable(run_parsing_node)


def test_run_parsing_node_maps_document_parsing_result(monkeypatch) -> None:
    from src.agents.parsing import node as parsing_node

    class FakeParsingAgent:
        def parse_documents(self, file_paths: list[str]) -> DocumentParsingResult:
            assert file_paths == ["/tmp/paper.pdf"]
            return DocumentParsingResult(
                markdown_content="# Parsed content",
                image_paths=["/tmp/page-1.png"],
                mineru_folder="mineru-output",
                parser_backend="mineru",
                parser_task_id="mineru-task-1",
                image_count=1,
            )

    monkeypatch.setattr(parsing_node, "get_document_parsing_agent", lambda: FakeParsingAgent())

    state = cast(
        SupervisorState,
        cast(
            object,
            {
                "file_paths": ["/tmp/paper.pdf"],
                "node_trace": {},
                "processing_steps": default_processing_steps(),
            },
        ),
    )

    result = parsing_node.run_parsing_node(state)
    result_dict = cast(dict[str, Any], cast(object, result))
    parsing_result = result_dict["parsing_result"]

    assert isinstance(parsing_result, dict)

    assert result["current_node"] == "parsing"
    assert result["parser_backend"] == "mineru"
    assert result["markdown_content"] == "# Parsed content"
    assert result["image_paths"] == ["/tmp/page-1.png"]
    assert parsing_result["mineru_folder"] == "mineru-output"


def test_run_parsing_node_accepts_markdown_fallback_without_file_paths() -> None:
    from src.agents.parsing import node as parsing_node

    state = cast(
        SupervisorState,
        cast(
            object,
            {
                "file_paths": [],
                "markdown_content": "# Downloaded content",
                "node_trace": {},
                "processing_steps": default_processing_steps(),
            },
        ),
    )

    result = parsing_node.run_parsing_node(state)
    result_dict = cast(dict[str, Any], cast(object, result))
    parsing_result = result_dict["parsing_result"]

    assert result["current_node"] == "parsing"
    assert result["parser_backend"] == "acquisition_fallback"
    assert result["markdown_content"] == "# Downloaded content"
    assert result["image_paths"] == []
    assert parsing_result == {
        "parser_backend": "acquisition_fallback",
        "markdown_content": "# Downloaded content",
        "image_paths": [],
    }
    assert result["node_trace"]["parsing"] == "success"
    assert result["processing_steps"]["parsing"]["status"] == "COMPLETED"


def test_translate_markdown_generates_terminology_plan(monkeypatch) -> None:
    agent = EvidenceAgent()
    calls: list[str] = []

    class FakeLLM:
        def invoke(self, messages):
            text = messages[-1].content
            calls.append(text)
            if "TERMINOLOGY_STAGE" in text:
                return AIMessage(content="GLA -> alpha-galactosidase A")
            if "STRUCTURE_STAGE" in text:
                return AIMessage(content="restore subject")
            return AIMessage(content="English draft")

    monkeypatch.setattr(agent, "get_translation_llm", lambda: FakeLLM())

    state = cast(
        Any,
        {
            "markdown_content": "GLA基因变异",
            "translated_md": "",
            "image_paths": [],
            "translation_required": False,
            "translation_terminology": "",
            "translation_structure": "",
            "translation_draft": "",
            "translation_polished": "",
            "translation_review": "",
            "translation_warnings": [],
            "image_descriptions": [],
        },
    )
    result = agent.translate_markdown(state)

    assert result["translation_terminology"] == "GLA -> alpha-galactosidase A"
    assert "TERMINOLOGY_STAGE" in calls[0]


def test_translate_markdown_generates_structure_plan(monkeypatch) -> None:
    agent = EvidenceAgent()

    class FakeLLM:
        def __init__(self):
            self.calls = []

        def invoke(self, messages):
            text = messages[-1].content
            self.calls.append(text)
            if "TERMINOLOGY_STAGE" in text:
                return AIMessage(content="term map")
            if "STRUCTURE_STAGE" in text:
                return AIMessage(content="1. restore subject\n2. split clauses")
            return AIMessage(content="English draft")

    fake = FakeLLM()
    monkeypatch.setattr(agent, "get_translation_llm", lambda: fake)

    result = agent.translate_markdown(
        cast(
            Any,
            {
                "markdown_content": "中文属于典型的意合语言……",
                "translated_md": "",
                "image_paths": [],
                "translation_required": False,
                "translation_terminology": "",
                "translation_structure": "",
                "translation_draft": "",
                "translation_polished": "",
                "translation_review": "",
                "translation_warnings": [],
                "image_descriptions": [],
            },
        )
    )

    assert result["translation_structure"] == "1. restore subject\n2. split clauses"


def test_translate_markdown_uses_terminology_and_structure_in_draft_stage(
    monkeypatch,
) -> None:
    agent = EvidenceAgent()
    prompts_seen: list[str] = []

    class FakeLLM:
        def invoke(self, messages):
            text = messages[-1].content
            prompts_seen.append(text)
            if "TERMINOLOGY_STAGE" in text:
                return AIMessage(content="GLA -> alpha-galactosidase A")
            if "STRUCTURE_STAGE" in text:
                return AIMessage(content="restore omitted subject")
            if "POLISH_STAGE" in text:
                return AIMessage(content="Translated English segment")
            return AIMessage(content="Translated English segment")

    monkeypatch.setattr(agent, "get_translation_llm", lambda: FakeLLM())
    result = agent.translate_markdown(
        cast(
            Any,
            {
                "markdown_content": "GLA基因变异导致...",
                "translated_md": "",
                "image_paths": [],
                "translation_required": False,
                "translation_terminology": "",
                "translation_structure": "",
                "translation_draft": "",
                "translation_polished": "",
                "translation_review": "",
                "translation_warnings": [],
                "image_descriptions": [],
            },
        )
    )

    assert result["translation_draft"]
    assert any("GLA -> alpha-galactosidase A" in prompt for prompt in prompts_seen)
    assert any("restore omitted subject" in prompt for prompt in prompts_seen)


def test_translate_markdown_stores_review_and_final_output(monkeypatch) -> None:
    agent = EvidenceAgent()

    class FakeLLM:
        def invoke(self, messages):
            text = messages[-1].content
            if "TERMINOLOGY_STAGE" in text:
                return AIMessage(content="term map")
            if "STRUCTURE_STAGE" in text:
                return AIMessage(content="structure plan")
            if "POLISH_STAGE" in text:
                return AIMessage(content="Polished English")
            if "REVIEW_STAGE" in text:
                return AIMessage(content="No unresolved ambiguity")
            return AIMessage(content="Draft English")

    monkeypatch.setattr(agent, "get_translation_llm", lambda: FakeLLM())

    result = agent.translate_markdown(
        cast(
            Any,
            {
                "markdown_content": "原文内容",
                "translated_md": "",
                "image_paths": [],
                "translation_required": False,
                "translation_terminology": "",
                "translation_structure": "",
                "translation_draft": "",
                "translation_polished": "",
                "translation_review": "",
                "translation_warnings": [],
                "image_descriptions": [],
            },
        )
    )

    assert result["translation_review"] == "No unresolved ambiguity"
    assert result["translated_md"] == "Polished English"
