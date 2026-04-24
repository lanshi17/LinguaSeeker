from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

from src.services.task_manager import (
    _SUPERVISOR_PROGRESS_NODES,
    _stream_supervisor_graph,
)
from src.agents.supervisor import translation


class _FakeGraph:
    """Mock graph whose ``astream`` yields pre-configured chunks."""

    def __init__(self, chunks: List[Dict[str, Any]], *, raise_at: int | None = None):
        self._chunks = chunks
        self._raise_at = raise_at

    async def astream(self, initial_state, *, config, stream_mode):
        for idx, chunk in enumerate(self._chunks):
            if self._raise_at is not None and idx == self._raise_at:
                raise RuntimeError(f"boom at chunk {idx}")
            yield chunk


def _make_config():
    return {"configurable": {"thread_id": "test-thread"}}


class TestStreamSupervisorGraph:
    @pytest.mark.asyncio
    async def test_happy_path_accumulates_state(self):
        chunks = [
            {"route_by_source": {"source": "upload"}},
            {"acquisition": {"file_paths": ["/a.pdf"]}},
            {"parsing": {"parsing_result": "ok"}},
            {"finalize": {"workflow_status": "COMPLETED"}},
        ]
        graph = _FakeGraph(chunks)
        pg = MagicMock()

        result = await _stream_supervisor_graph(
            graph, {"initial": True}, _make_config(), pg, "pt-1"
        )

        assert result["source"] == "upload"
        assert result["file_paths"] == ["/a.pdf"]
        assert result["parsing_result"] == "ok"
        assert result["workflow_status"] == "COMPLETED"

    @pytest.mark.asyncio
    async def test_logs_start_and_end_for_progress_nodes(self):
        chunks = [
            {"route_by_source": {"source": "upload"}},
            {"acquisition": {"file_paths": ["/a.pdf"]}},
            {"parsing": {"parsing_result": "ok"}},
            {"extraction": {"evidence_output": {}}},
            {"arbitration": {"acmg_result": {}}},
            {"finalize": {"workflow_status": "COMPLETED"}},
        ]
        graph = _FakeGraph(chunks)
        pg = MagicMock()

        with (
            patch("src.services.task_manager._log_node_start") as mock_start,
            patch("src.services.task_manager._log_node_end") as mock_end,
        ):
            await _stream_supervisor_graph(graph, None, _make_config(), pg, "pt-1")

        started = [c.args[2] for c in mock_start.call_args_list]
        assert started == ["acquisition", "parsing", "extraction", "arbitration"]

        ended = [c.args[2] for c in mock_end.call_args_list]
        assert ended == ["acquisition", "parsing", "extraction", "arbitration"]

        for c in mock_end.call_args_list:
            assert c.kwargs["success"] is True

    @pytest.mark.asyncio
    async def test_skips_logging_for_non_progress_nodes(self):
        chunks = [
            {"route_by_source": {"source": "web"}},
            {"finalize": {"workflow_status": "COMPLETED"}},
        ]
        graph = _FakeGraph(chunks)
        pg = MagicMock()

        with (
            patch("src.services.task_manager._log_node_start") as mock_start,
            patch("src.services.task_manager._log_node_end") as mock_end,
        ):
            await _stream_supervisor_graph(graph, None, _make_config(), pg, "pt-1")

        mock_start.assert_not_called()
        mock_end.assert_not_called()

    @pytest.mark.asyncio
    async def test_error_during_progress_node_logs_failure(self):
        chunks = [
            {"acquisition": {"file_paths": ["/a.pdf"]}},
            {"parsing": {"parsing_result": "ok"}},
        ]
        graph = _FakeGraph(chunks, raise_at=1)
        pg = MagicMock()

        with (
            patch("src.services.task_manager._log_node_start") as mock_start,
            patch("src.services.task_manager._log_node_end") as mock_end,
            pytest.raises(RuntimeError, match="boom at chunk 1"),
        ):
            await _stream_supervisor_graph(graph, None, _make_config(), pg, "pt-1")

        mock_start.assert_called_once_with(pg, "pt-1", "acquisition")

        assert mock_end.call_count == 1
        fail_call = mock_end.call_args
        assert fail_call.args == (pg, "pt-1", "acquisition")
        assert fail_call.kwargs["success"] is False
        assert fail_call.kwargs["error_code"] == "NODE_FAILURE"

    @pytest.mark.asyncio
    async def test_error_during_non_progress_node_skips_logging(self):
        chunks = [
            {"route_by_source": {"source": "upload"}},
        ]
        graph = _FakeGraph(chunks, raise_at=0)
        pg = MagicMock()

        with (
            patch("src.services.task_manager._log_node_start") as mock_start,
            patch("src.services.task_manager._log_node_end") as mock_end,
            pytest.raises(RuntimeError),
        ):
            await _stream_supervisor_graph(graph, None, _make_config(), pg, "pt-1")

        mock_start.assert_not_called()
        mock_end.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_graph_returns_empty_state(self):
        graph = _FakeGraph([])
        pg = MagicMock()

        result = await _stream_supervisor_graph(graph, None, _make_config(), pg, "pt-1")

        assert result == {}

    @pytest.mark.asyncio
    async def test_none_initial_state_passed_to_astream(self):
        graph = _FakeGraph([{"finalize": {"done": True}}])
        pg = MagicMock()

        with patch.object(graph, "astream", wraps=graph.astream) as spy:
            await _stream_supervisor_graph(graph, None, _make_config(), pg, "pt-1")
            spy.assert_called_once()
            assert spy.call_args.args[0] is None

    @pytest.mark.asyncio
    async def test_non_dict_node_output_skipped(self):
        chunks = [
            {"acquisition": "scalar_value"},
            {"parsing": {"parsing_result": "ok"}},
        ]
        graph = _FakeGraph(chunks)
        pg = MagicMock()

        result = await _stream_supervisor_graph(graph, None, _make_config(), pg, "pt-1")

        assert "parsing_result" in result
        assert "scalar_value" not in result.values()

    @pytest.mark.asyncio
    async def test_translation_skipped_only_progress_nodes_logged(self):
        chunks = [
            {"acquisition": {"file_paths": ["/a.pdf"]}},
            {"parsing": {"parsing_result": "ok"}},
            {"extraction": {"evidence": {}}},
            {"arbitration": {"acmg_result": {}}},
            {"finalize": {"workflow_status": "COMPLETED"}},
        ]
        graph = _FakeGraph(chunks)
        pg = MagicMock()

        with (
            patch("src.services.task_manager._log_node_start") as mock_start,
            patch("src.services.task_manager._log_node_end"),
        ):
            await _stream_supervisor_graph(graph, None, _make_config(), pg, "pt-1")

        started = [c.args[2] for c in mock_start.call_args_list]
        assert "translation" not in started
        assert started == ["acquisition", "parsing", "extraction", "arbitration"]


class TestSupervisorProgressNodes:
    def test_supervisor_translation_still_skips_when_existing_translation_is_valid(self):
        state = {
            "markdown_content": "English source text",
            "translated_markdown": "Valid English translation",
            "image_paths": [],
            "image_descriptions": [],
        }

        updated = translation(state)

        assert updated["translated_markdown"] == "Valid English translation"
        assert updated.get("translation_review", "") == ""

    def test_progress_nodes_set_contains_expected_nodes(self):
        expected = {
            "acquisition",
            "parsing",
            "translation",
            "extraction",
            "reasoning",
            "arbitration",
        }
        assert _SUPERVISOR_PROGRESS_NODES == expected

    def test_non_progress_nodes_excluded(self):
        non_progress = {
            "route_by_source",
            "interaction",
            "finalize",
            "finalize_failed",
            "human_review",
        }
        assert _SUPERVISOR_PROGRESS_NODES.isdisjoint(non_progress)


class TestProcessingNodeMapping:
    def test_arbitration_maps_to_adjudication(self):
        from src.services.enum import PROCESSING_NODE_TO_STEP

        assert PROCESSING_NODE_TO_STEP["arbitration"] == "adjudication"

    def test_all_progress_nodes_have_mappings(self):
        from src.services.enum import PROCESSING_NODE_TO_STEP

        for node in _SUPERVISOR_PROGRESS_NODES:
            if node == "reasoning":
                assert node not in PROCESSING_NODE_TO_STEP
                continue
            assert node in PROCESSING_NODE_TO_STEP, f"Missing mapping for '{node}'"
