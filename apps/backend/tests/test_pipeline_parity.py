from __future__ import annotations

from typing import Any


class TestResolveThreadId:
    def test_request_id_is_primary(self):
        from src.services.task_manager import _resolve_supervisor_thread_id

        assert _resolve_supervisor_thread_id("req-1", "2", "3") == "req-1"

    def test_paper_task_id_fallback(self):
        from src.services.task_manager import _resolve_supervisor_thread_id

        result = _resolve_supervisor_thread_id("", "42", "3")
        assert result == "42"

    def test_document_id_fallback(self):
        from src.services.task_manager import _resolve_supervisor_thread_id

        result = _resolve_supervisor_thread_id("", "", "99")
        assert result == "99"

    def test_default_fallback(self):
        from src.services.task_manager import _resolve_supervisor_thread_id

        result = _resolve_supervisor_thread_id("", "", "")
        assert result == "supervisor-thread"

    def test_none_values_fallback(self):
        from src.services.task_manager import _resolve_supervisor_thread_id

        result = _resolve_supervisor_thread_id(None, None, None)  # type: ignore[arg-type]
        assert result == "supervisor-thread"

    def test_whitespace_only_falls_through(self):
        from src.services.task_manager import _resolve_supervisor_thread_id

        result = _resolve_supervisor_thread_id("  ", "", "7")
        assert result == "7"


class TestBuildSupervisorPayload:
    def test_payload_extracts_evidence_fields(self):
        from src.services.task_manager import _build_supervisor_payload

        evidence = {"ps3_evidence": {}, "status": "done"}

        final_state: dict[str, Any] = {
            "evidence_output": evidence,
            "workflow_status": "completed",
            "requires_human_review": False,
            "acmg_result": {"classification": "PS3_moderate"},
            "errors": [],
            "warnings": [],
            "node_trace": {"acquisition": "done"},
            "graph_sync_result": {"synced": True},
        }

        result = _build_supervisor_payload(
            final_state=final_state,
            source="upload",
            document_id="1",
            paper_task_id="2",
            request_id="req-1",
            file_hash="abc123",
            file_size_bytes=4096,
        )

        # source is NOT included in the payload — only used for conditional logic
        assert "source" not in result
        assert result["document_id"] == "1"
        assert result["paper_task_id"] == "2"
        assert result["request_id"] == "req-1"
        assert result["status"] == "success"
        assert result["workflow_status"] == "completed"
        assert result["requires_human_review"] is False
        assert result["node_trace"] == {"acquisition": "done"}
        assert result["graph_sync_result"] == {"synced": True}
        # upload source adds file metadata
        assert result["file_hash"] == "abc123"
        assert result["file_size_bytes"] == 4096
        # evidence is serialized
        assert "evidence" in result

    def test_payload_handles_no_evidence_output(self):
        from src.services.task_manager import _build_supervisor_payload

        final_state: dict[str, Any] = {
            "evidence_output": None,
            "workflow_status": "FAILED",
            "requires_human_review": False,
            "acmg_result": None,
            "errors": ["parse failed"],
            "warnings": [],
            "node_trace": {},
            "graph_sync_result": {},
        }

        result = _build_supervisor_payload(
            final_state=final_state,
            source="pubmed",
            document_id="5",
            paper_task_id="10",
            request_id="req-2",
        )

        assert "source" not in result
        assert result["document_id"] == "5"
        assert result["paper_task_id"] == "10"
        assert result["request_id"] == "req-2"
        assert result["status"] == "failed"
        assert result["requires_human_review"] is False
        # no evidence key when evidence_output is None
        assert "evidence" not in result
        # failed status adds error fields
        assert "error_code" in result or "error_message" in result
