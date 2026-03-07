from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from src.domain.models import (
    DocumentParsingArtifact,
    DocumentParsingResult,
    EvidenceOutput,
    PipelineFiles,
)
from src.service import tasks as tasks_module


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
