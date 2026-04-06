from __future__ import annotations

from types import SimpleNamespace
from typing import Any, AsyncIterator, Dict, List

import pytest

from src.domain.models import (
    DocumentParsingArtifact,
    DocumentParsingResult,
    EvidenceOutput,
    PipelineFiles,
)
from src.services import task_manager as tasks_module


class _FakeGraphBase:
    """Base class providing ``astream`` backed by ``ainvoke``."""

    async def ainvoke(self, _state: Any, config: Dict[str, Any] | None = None) -> Dict[str, Any]:
        raise NotImplementedError

    async def astream(
        self,
        state: Any,
        *,
        config: Dict[str, Any] | None = None,
        stream_mode: str = "values",
    ) -> AsyncIterator[Dict[str, Dict[str, Any]]]:
        result = await self.ainvoke(state, config=config)
        yield {"__result__": result}


def _make_evidence_output(ps3_evidence: Dict[str, Any] | None = None) -> EvidenceOutput:
    return EvidenceOutput(
        ps3_evidence=ps3_evidence or {},
        arbitration_confidence=0.0,
        image_descriptions=[],
        final_evidence_strength="",
        status="success",
        origin_format_md="",
        en_format_md="",
        extracted_fields={},
        field_confidence_scores={},
        overall_confidence=0.0,
        evidence_classification="",
        acmg_evidence_levels=[],
    )


def _make_parsing_result(mineru_folder: str) -> DocumentParsingResult:
    return DocumentParsingResult(
        markdown_content="md content",
        image_paths=["/img.jpg"],
        mineru_folder=mineru_folder,
        parser_backend="mineru",
        parser_task_id="mineru-task-1",
        image_count=1,
        artifacts=DocumentParsingArtifact(
            markdown_object_key=f"{mineru_folder}/parsed_markdown.md",
            markdown_url=f"/api/v1/results/doc-1/{mineru_folder}/parsed_markdown.md",
            image_object_keys=[f"{mineru_folder}/images/image1.jpg"],
        ),
    )


def _invoke_bound_task(task: Any, *args: Any, **kwargs: Any) -> Any:
    return task(*args, **kwargs)


async def _fake_init_kb() -> bool:
    return True


def test_process_pdf_task_flag_off_uses_legacy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    evidence = _make_evidence_output(ps3_evidence={"ok": True})
    saved_files = PipelineFiles(
        origin_md_path="/tmp/orig.md",
        en_md_path="/tmp/en.md",
        image_desc_path="/tmp/image_desc.txt",
        ps3_evidence_path="/tmp/ps3.json",
        image_dir="/tmp/images",
        origin_md_url="",
        en_md_url="",
        image_desc_url="",
        ps3_evidence_url="",
        image_urls=[],
    )
    called = {"legacy": False, "supervisor": False}

    def fake_acquisition(pg: Any, ptid: str, fps: List[str], nt: Dict[str, str]) -> Any:
        called["legacy"] = True
        nt["acquisition"] = "success"
        return fps, nt

    async def fake_parsing(pg: Any, ptid: str, fps: List[str], nt: Dict[str, str]) -> Any:
        nt["parsing"] = "success"
        return _make_parsing_result("/tmp/mineru-output"), nt

    def fake_translation(pg: Any, ptid: str, md: str, nt: Dict[str, str]) -> Any:
        nt["translation"] = "success"
        return md, "en text", nt, []

    def fake_extraction(
        pg: Any, ptid: str, source: str, en: str, imgs: List[str], nt: Dict[str, str]
    ) -> Any:
        nt["extraction"] = "success"
        return evidence, nt

    def fake_acmg(pg: Any, ptid: str, did: str, resp: Any, nt: Dict[str, str]) -> Any:
        nt["acmg"] = "success"
        return {"pg_evidence_id": 1, "neo4j_synced": True}, nt

    async def fake_store(*_: Any, **__: Any) -> PipelineFiles:
        return saved_files

    async def fake_store_parsing(*_: Any, **__: Any) -> DocumentParsingArtifact:
        return DocumentParsingArtifact(
            markdown_object_key="doc-1/parsing/parsed_markdown.md",
            markdown_url="/api/v1/results/doc-1/doc-1/parsing/parsed_markdown.md",
            image_object_keys=["doc-1/parsing/images/img.jpg"],
        )

    def fake_supervisor(**_: Any) -> Dict[str, Any]:
        called["supervisor"] = True
        return {"status": "unexpected"}

    monkeypatch.setattr(
        tasks_module.cfg.__class__,
        "use_agent_workflow",
        lambda self, task_type: False,
    )
    monkeypatch.setattr(tasks_module, "_run_supervisor_pipeline", fake_supervisor)
    monkeypatch.setattr(tasks_module, "run_node_acquisition", fake_acquisition)
    monkeypatch.setattr(tasks_module, "run_node_parsing", fake_parsing)
    monkeypatch.setattr(tasks_module, "run_node_translation", fake_translation)
    monkeypatch.setattr(tasks_module, "run_node_extraction", fake_extraction)
    monkeypatch.setattr(tasks_module, "run_node_acmg", fake_acmg)
    monkeypatch.setattr(tasks_module, "_store_outputs_in_minio", fake_store)
    monkeypatch.setattr(tasks_module, "_store_parsing_artifacts_in_minio", fake_store_parsing)
    monkeypatch.setattr(tasks_module, "init_knowledge_base_if_needed", _fake_init_kb)
    monkeypatch.setattr(tasks_module, "get_postgres_client", lambda: SimpleNamespace())
    monkeypatch.setattr(tasks_module.file_utils, "cleanup_old_temp_folders", lambda *_, **__: None)

    result = _invoke_bound_task(tasks_module.process_pdf_task, ["file.pdf"])

    assert called == {"legacy": True, "supervisor": False}
    assert result["graph_sync_result"] == {"pg_evidence_id": 1, "neo4j_synced": True}


def test_process_pdf_task_flag_on_uses_supervisor_path(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"legacy": False, "supervisor": False}

    def fail_legacy(*_: Any, **__: Any) -> Any:
        called["legacy"] = True
        raise AssertionError("legacy path should not run when supervisor flag is enabled")

    def fake_supervisor(**kwargs: Any) -> Dict[str, Any]:
        called["supervisor"] = True
        assert kwargs["source"] == "upload"
        assert kwargs["file_paths"] == ["file.pdf"]
        return {
            "document_id": kwargs["document_id"],
            "paper_task_id": kwargs["paper_task_id"],
            "status": "success",
            "graph_sync_result": {"pg_evidence_id": 7, "neo4j_synced": True},
        }

    monkeypatch.setattr(
        tasks_module.cfg.__class__,
        "use_agent_workflow",
        lambda self, task_type: task_type == "pdf",
    )
    monkeypatch.setattr(tasks_module, "_run_supervisor_pipeline", fake_supervisor)
    monkeypatch.setattr(tasks_module, "run_node_acquisition", fail_legacy)
    monkeypatch.setattr(tasks_module, "init_knowledge_base_if_needed", _fake_init_kb)
    monkeypatch.setattr(tasks_module, "get_postgres_client", lambda: SimpleNamespace())
    monkeypatch.setattr(tasks_module.file_utils, "cleanup_old_temp_folders", lambda *_, **__: None)

    result = _invoke_bound_task(tasks_module.process_pdf_task, ["file.pdf"])

    assert called == {"legacy": False, "supervisor": True}
    assert result["status"] == "success"
    assert result["graph_sync_result"] == {"pg_evidence_id": 7, "neo4j_synced": True}


@pytest.mark.parametrize(
    ("task", "task_arg", "task_type", "payload_key"),
    [
        (tasks_module.process_pubmed_paper_task, "12345", "pubmed", "pmids"),
        (
            tasks_module.process_web_page_task,
            "https://example.com/article",
            "web",
            "urls",
        ),
    ],
)
def test_non_pdf_tasks_flag_on_use_supervisor_path(
    monkeypatch: pytest.MonkeyPatch,
    task: Any,
    task_arg: str,
    task_type: str,
    payload_key: str,
) -> None:
    called = {"supervisor": False}

    def fail_legacy(*_: Any, **__: Any) -> Any:
        raise AssertionError(
            "legacy acquisition path should not run when supervisor flag is enabled"
        )

    def fake_supervisor(**kwargs: Any) -> Dict[str, Any]:
        called["supervisor"] = True
        assert kwargs["source"] == task_type
        assert kwargs[payload_key] == [task_arg]
        return {
            "document_id": kwargs["document_id"],
            "paper_task_id": kwargs["paper_task_id"],
            "status": "success",
            "graph_sync_result": {},
        }

    monkeypatch.setattr(
        tasks_module.cfg.__class__,
        "use_agent_workflow",
        lambda self, query_type: query_type == task_type,
    )
    monkeypatch.setattr(tasks_module, "_run_supervisor_pipeline", fake_supervisor)
    monkeypatch.setattr(tasks_module, "get_postgres_client", lambda: SimpleNamespace())
    if task_type == "pubmed":
        monkeypatch.setattr(tasks_module, "get_pubmed_service", fail_legacy)
    else:
        monkeypatch.setattr(tasks_module, "get_firecrawl_service", fail_legacy)

    result = _invoke_bound_task(task, task_arg, None, None, None)

    assert called["supervisor"] is True
    assert result["status"] == "success"


def test_run_supervisor_pipeline_passes_interrupt_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: Dict[str, Any] = {}

    class FakeGraph(_FakeGraphBase):
        async def ainvoke(
            self, _state: Any, config: Dict[str, Any] | None = None
        ) -> Dict[str, Any]:
            captured["ainvoke_config"] = config
            return {
                "workflow_status": "completed",
                "node_trace": {},
                "evidence_output": None,
            }

    def fake_compile_supervisor(
        *,
        interrupt_before_human_review: bool = False,
        checkpointer: Any | None = None,
    ) -> FakeGraph:
        captured["interrupt_before_human_review"] = interrupt_before_human_review
        captured["checkpointer"] = checkpointer
        return FakeGraph()

    import src.agents.supervisor as supervisor_module

    monkeypatch.setattr(
        tasks_module.cfg,
        "agent_workflow_interrupt_before_human_review",
        True,
        raising=False,
    )
    monkeypatch.setattr(supervisor_module, "compile_supervisor", fake_compile_supervisor)

    result = tasks_module._run_supervisor_pipeline(
        source="upload",
        document_id="1",
        paper_task_id="2",
        request_id="req-1",
        postgres=SimpleNamespace(),
        file_paths=["/tmp/paper.pdf"],
    )

    assert captured["interrupt_before_human_review"] is True
    assert captured["checkpointer"] is not None
    assert captured["ainvoke_config"] == {"configurable": {"thread_id": "req-1"}}
    assert result["status"] == "success"


def test_run_supervisor_pipeline_falls_back_thread_id(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: Dict[str, Any] = {}

    class FakeGraph(_FakeGraphBase):
        async def ainvoke(
            self, _state: Any, config: Dict[str, Any] | None = None
        ) -> Dict[str, Any]:
            captured["ainvoke_config"] = config
            return {
                "workflow_status": "completed",
                "node_trace": {},
                "evidence_output": None,
            }

    def fake_compile_supervisor(
        *,
        interrupt_before_human_review: bool = False,
        checkpointer: Any | None = None,
    ) -> FakeGraph:
        captured["interrupt_before_human_review"] = interrupt_before_human_review
        captured["checkpointer"] = checkpointer
        return FakeGraph()

    import src.agents.supervisor as supervisor_module

    monkeypatch.setattr(
        tasks_module.cfg,
        "agent_workflow_interrupt_before_human_review",
        True,
        raising=False,
    )
    monkeypatch.setattr(supervisor_module, "compile_supervisor", fake_compile_supervisor)

    result = tasks_module._run_supervisor_pipeline(
        source="upload",
        document_id="doc-1",
        paper_task_id="paper-2",
        request_id="",
        postgres=SimpleNamespace(),
        file_paths=["/tmp/paper.pdf"],
    )

    assert captured["interrupt_before_human_review"] is True
    assert captured["checkpointer"] is not None
    assert captured["ainvoke_config"] == {"configurable": {"thread_id": "paper-2"}}
    assert result["status"] == "success"


def test_run_supervisor_pipeline_falls_back_to_document_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: Dict[str, Any] = {}

    class FakeGraph(_FakeGraphBase):
        async def ainvoke(
            self, _state: Any, config: Dict[str, Any] | None = None
        ) -> Dict[str, Any]:
            captured["ainvoke_config"] = config
            return {
                "workflow_status": "completed",
                "node_trace": {},
                "evidence_output": None,
            }

    def fake_compile_supervisor(
        *,
        interrupt_before_human_review: bool = False,
        checkpointer: Any | None = None,
    ) -> FakeGraph:
        captured["interrupt_before_human_review"] = interrupt_before_human_review
        captured["checkpointer"] = checkpointer
        return FakeGraph()

    import src.agents.supervisor as supervisor_module

    monkeypatch.setattr(
        tasks_module.cfg,
        "agent_workflow_interrupt_before_human_review",
        True,
        raising=False,
    )
    monkeypatch.setattr(supervisor_module, "compile_supervisor", fake_compile_supervisor)

    result = tasks_module._run_supervisor_pipeline(
        source="upload",
        document_id="doc-1",
        paper_task_id="",
        request_id="",
        postgres=SimpleNamespace(),
        file_paths=["/tmp/paper.pdf"],
    )

    assert captured["interrupt_before_human_review"] is True
    assert captured["checkpointer"] is not None
    assert captured["ainvoke_config"] == {"configurable": {"thread_id": "doc-1"}}
    assert result["status"] == "success"


def test_run_supervisor_pipeline_uses_default_thread_id_when_all_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: Dict[str, Any] = {}

    class FakeGraph(_FakeGraphBase):
        async def ainvoke(
            self, _state: Any, config: Dict[str, Any] | None = None
        ) -> Dict[str, Any]:
            captured["ainvoke_config"] = config
            return {
                "workflow_status": "completed",
                "node_trace": {},
                "evidence_output": None,
            }

    def fake_compile_supervisor(
        *,
        interrupt_before_human_review: bool = False,
        checkpointer: Any | None = None,
    ) -> FakeGraph:
        captured["interrupt_before_human_review"] = interrupt_before_human_review
        captured["checkpointer"] = checkpointer
        return FakeGraph()

    import src.agents.supervisor as supervisor_module

    monkeypatch.setattr(
        tasks_module.cfg,
        "agent_workflow_interrupt_before_human_review",
        True,
        raising=False,
    )
    monkeypatch.setattr(supervisor_module, "compile_supervisor", fake_compile_supervisor)

    result = tasks_module._run_supervisor_pipeline(
        source="upload",
        document_id="",
        paper_task_id="",
        request_id="",
        postgres=SimpleNamespace(),
        file_paths=["/tmp/paper.pdf"],
    )

    assert captured["interrupt_before_human_review"] is True
    assert captured["checkpointer"] is not None
    assert captured["ainvoke_config"] == {"configurable": {"thread_id": "supervisor-thread"}}
    assert result["status"] == "success"


def test_run_supervisor_pipeline_reuses_checkpointer_when_interrupt_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: Dict[str, Any] = {"checkpointers": []}

    class FakeGraph(_FakeGraphBase):
        async def ainvoke(
            self, _state: Any, config: Dict[str, Any] | None = None
        ) -> Dict[str, Any]:
            captured["ainvoke_config"] = config
            return {
                "workflow_status": "completed",
                "node_trace": {},
                "evidence_output": None,
            }

    def fake_compile_supervisor(
        *,
        interrupt_before_human_review: bool = False,
        checkpointer: Any | None = None,
    ) -> FakeGraph:
        captured["interrupt_before_human_review"] = interrupt_before_human_review
        captured["checkpointers"].append(checkpointer)
        return FakeGraph()

    import src.agents.supervisor as supervisor_module

    monkeypatch.setattr(
        tasks_module.cfg,
        "agent_workflow_interrupt_before_human_review",
        True,
        raising=False,
    )
    monkeypatch.setattr(tasks_module, "_supervisor_memory_checkpointer", None, raising=False)
    monkeypatch.setattr(supervisor_module, "compile_supervisor", fake_compile_supervisor)

    tasks_module._run_supervisor_pipeline(
        source="upload",
        document_id="d1",
        paper_task_id="p1",
        request_id="r1",
        postgres=SimpleNamespace(),
        file_paths=["/tmp/paper.pdf"],
    )
    tasks_module._run_supervisor_pipeline(
        source="upload",
        document_id="d2",
        paper_task_id="p2",
        request_id="r2",
        postgres=SimpleNamespace(),
        file_paths=["/tmp/paper.pdf"],
    )

    assert captured["interrupt_before_human_review"] is True
    assert len(captured["checkpointers"]) == 2
    assert captured["checkpointers"][0] is captured["checkpointers"][1]


def test_run_supervisor_pipeline_marks_pending_review_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeGraph(_FakeGraphBase):
        async def ainvoke(
            self, _state: Any, config: Dict[str, Any] | None = None
        ) -> Dict[str, Any]:
            return {
                "workflow_status": "PENDING",
                "requires_human_review": True,
                "node_trace": {"arbitration": "success"},
                "evidence_output": None,
            }

    def fake_compile_supervisor(
        *,
        interrupt_before_human_review: bool = False,
        checkpointer: Any | None = None,
    ) -> FakeGraph:
        return FakeGraph()

    import src.agents.supervisor as supervisor_module

    monkeypatch.setattr(supervisor_module, "compile_supervisor", fake_compile_supervisor)

    result = tasks_module._run_supervisor_pipeline(
        source="upload",
        document_id="1",
        paper_task_id="2",
        request_id="req-review",
        postgres=SimpleNamespace(),
        file_paths=["/tmp/paper.pdf"],
    )

    assert result["status"] == "pending_review"
    assert result["requires_human_review"] is True


def test_resume_supervisor_pipeline_success(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: Dict[str, Any] = {}

    class FakeGraph(_FakeGraphBase):
        async def ainvoke(
            self,
            _state: Any,
            config: Dict[str, Any] | None = None,
        ) -> Dict[str, Any]:
            captured["ainvoke_config"] = config
            return {
                "workflow_status": "COMPLETED",
                "requires_human_review": False,
                "node_trace": {"human_review": "completed"},
                "evidence_output": {"summary": "ok"},
            }

    def fake_compile_supervisor(
        *,
        interrupt_before_human_review: bool = False,
        checkpointer: Any | None = None,
    ) -> FakeGraph:
        captured["interrupt_before_human_review"] = interrupt_before_human_review
        captured["checkpointer"] = checkpointer
        return FakeGraph()

    import src.agents.supervisor as supervisor_module

    monkeypatch.setattr(supervisor_module, "compile_supervisor", fake_compile_supervisor)
    monkeypatch.setattr(tasks_module, "_supervisor_memory_checkpointer", object(), raising=False)

    result = tasks_module._resume_supervisor_pipeline(
        source="upload",
        document_id="doc-1",
        paper_task_id="paper-2",
        request_id="req-3",
        postgres=SimpleNamespace(),
    )

    assert captured["interrupt_before_human_review"] is True
    assert captured["checkpointer"] is tasks_module._supervisor_memory_checkpointer
    assert captured["ainvoke_config"] == {"configurable": {"thread_id": "req-3"}}
    assert result["status"] == "success"
    assert result["workflow_status"] == "COMPLETED"


def test_resume_supervisor_pipeline_without_checkpoint_returns_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeGraph(_FakeGraphBase):
        async def ainvoke(
            self,
            _state: Any,
            config: Dict[str, Any] | None = None,
        ) -> Dict[str, Any]:
            from langgraph.errors import EmptyInputError

            raise EmptyInputError("no checkpoint")

        async def astream(
            self,
            state: Any,
            *,
            config: Dict[str, Any] | None = None,
            stream_mode: str = "values",
        ) -> AsyncIterator[Dict[str, Dict[str, Any]]]:
            from langgraph.errors import EmptyInputError

            raise EmptyInputError("no checkpoint")
            yield  # type: ignore[misc]

    def fake_compile_supervisor(
        *,
        interrupt_before_human_review: bool = False,
        checkpointer: Any | None = None,
    ) -> FakeGraph:
        return FakeGraph()

    import src.agents.supervisor as supervisor_module

    monkeypatch.setattr(supervisor_module, "compile_supervisor", fake_compile_supervisor)
    monkeypatch.setattr(tasks_module, "_supervisor_memory_checkpointer", object(), raising=False)

    result = tasks_module._resume_supervisor_pipeline(
        source="upload",
        document_id="doc-1",
        paper_task_id="paper-2",
        request_id="req-3",
        postgres=SimpleNamespace(),
    )

    assert result["status"] == "failed"
    assert result["error_code"] == "RESOURCE_NOT_FOUND"
    assert "No paused workflow state found" in result["error_message"]
