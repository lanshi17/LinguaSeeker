from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from src.domain.agent.document_parsing import DocumentParsingAgent
from src.domain.models import MinerUResponse


@pytest.fixture()
def parsed_folder(tmp_path: Path) -> Path:
    folder = tmp_path / "parsed"
    folder.mkdir()
    (folder / "full.md").write_text("parsed markdown", encoding="utf-8")
    (folder / "page-1.jpg").write_bytes(b"jpg")
    return folder


def test_document_parsing_agent_mineru_success(parsed_folder: Path) -> None:
    class FakeMinerUComponent:
        def minerU_pipeline(self, request: Any) -> MinerUResponse:
            assert request.file_paths == ["paper.pdf"]
            return MinerUResponse(
                task_id="mineru-task-1",
                status="done",
                message=None,
                folder_path=str(parsed_folder),
            )

    agent = DocumentParsingAgent(parser_component=FakeMinerUComponent())
    result = agent.parse_documents(["paper.pdf"])

    assert result.markdown_content == "parsed markdown"
    assert result.parser_backend == "mineru"
    assert result.parser_task_id == "mineru-task-1"
    assert result.image_count == 1
    assert result.image_paths == [str(parsed_folder / "page-1.jpg")]


def test_document_parsing_agent_collects_normalized_markdown(parsed_folder: Path) -> None:
    (parsed_folder / "full.md").write_text("# Title\n\n<div>debug</div>\n\n正文", encoding="utf-8")

    class FakeMinerUComponent:
        def minerU_pipeline(self, request: Any) -> MinerUResponse:
            return MinerUResponse(
                task_id="mineru-task-1",
                status="done",
                message=None,
                folder_path=str(parsed_folder),
            )

    agent = DocumentParsingAgent(parser_component=FakeMinerUComponent())
    result = agent.parse_documents(["paper.pdf"])

    assert result.markdown_content == "# Title\n\n正文"


def test_document_parsing_agent_falls_back_to_paddleocr(
    parsed_folder: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeMinerUComponent:
        def minerU_pipeline(self, request: Any) -> None:
            assert request.file_paths == ["paper.pdf"]
            return None

    monkeypatch.setattr(
        "src.domain.agent.document_parsing.run_paddleocr_fallback",
        lambda file_paths: MinerUResponse(
            task_id="ocr-task-1",
            status="done",
            message=None,
            folder_path=str(parsed_folder),
        ),
    )

    agent = DocumentParsingAgent(parser_component=FakeMinerUComponent())
    result = agent.parse_documents(["paper.pdf"])

    assert result.parser_backend == "paddleocr"
    assert result.parser_task_id == "ocr-task-1"
    assert result.mineru_folder == str(parsed_folder)
