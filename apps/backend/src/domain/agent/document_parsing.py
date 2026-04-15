from __future__ import annotations

from pathlib import Path
from typing import Any, List, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from src.domain.document_normalization import normalize_document_body
from src.domain.mineru.component import MinerUComponent, run_paddleocr_fallback
from src.domain.models import (
    DocumentParsingArtifact,
    DocumentParsingResult,
    MinerURequest,
    MinerUResponse,
)
import src.utils.exceptions as exc


class DocumentParsingState(TypedDict, total=False):
    file_paths: List[str]
    parser_response: MinerUResponse
    parser_backend: str
    parsing_result: DocumentParsingResult


def collect_parsing_assets(folder_path: str) -> tuple[str, List[str]]:
    root = Path(folder_path)
    markdown_path = root / "full.md"
    if not markdown_path.exists():
        markdown_candidates = sorted(root.rglob("*.md"))
        if not markdown_candidates:
            raise exc.ParsingException("Parser returned no markdown content")
        markdown_path = markdown_candidates[0]

    markdown_content = markdown_path.read_text(encoding="utf-8")
    normalized = normalize_document_body(markdown_content)
    image_paths = [str(path) for path in sorted(root.rglob("*.jpg"))]
    return normalized.text, image_paths


class DocumentParsingAgent:
    def __init__(self, parser_component: Optional[Any] = None) -> None:
        self._parser_component = parser_component or MinerUComponent()

        graph = StateGraph(DocumentParsingState)
        graph.add_node("validate", self._validate)
        graph.add_node("parse", self._parse)
        graph.add_node("collect", self._collect)
        graph.add_edge(START, "validate")
        graph.add_edge("validate", "parse")
        graph.add_edge("parse", "collect")
        graph.add_edge("collect", END)
        self._graph = graph.compile()

    def parse_documents(self, file_paths: List[str]) -> DocumentParsingResult:
        state = self._graph.invoke({"file_paths": file_paths})
        parsing_result = state.get("parsing_result")
        if parsing_result is None:
            raise exc.ParsingException("Parser returned no structured result")
        return parsing_result

    def _validate(self, state: DocumentParsingState) -> DocumentParsingState:
        file_paths = [
            str(path).strip() for path in state.get("file_paths", []) if str(path).strip()
        ]
        if not file_paths:
            raise exc.ValidationException("No files provided for parsing")
        return {"file_paths": file_paths}

    def _parse(self, state: DocumentParsingState) -> DocumentParsingState:
        file_paths = state.get("file_paths", [])
        mineru_request = MinerURequest(file_paths=file_paths, callback=None)
        mineru_exception: Optional[Exception] = None

        try:
            mineru_response = self._parser_component.minerU_pipeline(mineru_request)
            if mineru_response and mineru_response.folder_path:
                return {
                    "parser_response": mineru_response,
                    "parser_backend": "mineru",
                }
        except Exception as exc_info:
            mineru_exception = exc_info

        try:
            fallback_response = run_paddleocr_fallback(file_paths)
            if fallback_response and fallback_response.folder_path:
                return {
                    "parser_response": fallback_response,
                    "parser_backend": "paddleocr",
                }
        except Exception as fallback_exc:
            raise exc.ParsingException(f"All parsers failed: {fallback_exc}") from fallback_exc

        if mineru_exception is not None:
            raise exc.ParsingException(f"Parser failed: {mineru_exception}") from mineru_exception
        raise exc.ParsingException("Parser returned no folder")

    def _collect(self, state: DocumentParsingState) -> DocumentParsingState:
        parser_response = state.get("parser_response")
        parser_backend = state.get("parser_backend", "mineru")
        if parser_response is None or not parser_response.folder_path:
            raise exc.ParsingException("Parser returned no folder")

        markdown_content, image_paths = collect_parsing_assets(parser_response.folder_path)
        return {
            "parsing_result": DocumentParsingResult(
                markdown_content=markdown_content,
                image_paths=image_paths,
                mineru_folder=parser_response.folder_path,
                parser_backend=parser_backend,
                parser_task_id=parser_response.task_id,
                image_count=len(image_paths),
                artifacts=DocumentParsingArtifact(
                    markdown_object_key=None,
                    markdown_url=None,
                ),
            )
        }


_document_parsing_agent: Optional[DocumentParsingAgent] = None


def get_document_parsing_agent() -> DocumentParsingAgent:
    global _document_parsing_agent
    if _document_parsing_agent is None:
        _document_parsing_agent = DocumentParsingAgent()
    return _document_parsing_agent
