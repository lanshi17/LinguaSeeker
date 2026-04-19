from __future__ import annotations

from typing import Any, cast

from src.domain.agent.document_parsing import DocumentParsingAgent as LegacyDocumentParsingAgent
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
