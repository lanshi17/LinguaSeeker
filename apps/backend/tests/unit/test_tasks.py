import os
from pathlib import Path
from typing import Any, Dict, List
from types import SimpleNamespace

import pytest

from src.domain.graph.sync import SchemaSyncError
from src.service import tasks as tasks_module
from src.domain.models import (
    DocumentParsingArtifact,
    DocumentParsingResult,
    EvidenceOutput,
    PipelineFiles,
)
import src.utils.exceptions as exc


def _make_mineru_folder(tmp_path: Path) -> Path:
    folder = tmp_path / "mineru_output"
    folder.mkdir()
    (folder / "full.md").write_text("hello world", encoding="utf-8")
    image_path = folder / "image1.jpg"
    image_path.write_bytes(b"fake")
    return folder


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


def _make_managed_upload_file(tmp_path: Path, name: str = "sample.pdf") -> str:
    workdir = tmp_path / "run_upload_test"
    workdir.mkdir(parents=True, exist_ok=True)
    file_path = workdir / name
    file_path.write_bytes(b"%PDF-1.7 test")
    return str(file_path)


@pytest.fixture()
def mineru_folder(tmp_path: Path) -> Path:
    return _make_mineru_folder(tmp_path)


def test_disable_proxies() -> None:
    os.environ["http_proxy"] = "1"
    os.environ["https_proxy"] = "1"
    os.environ["all_proxy"] = "1"
    tasks_module._disable_proxies()
    assert "http_proxy" not in os.environ
    assert "https_proxy" not in os.environ
    assert "all_proxy" not in os.environ


def test_collect_mineru_assets(mineru_folder: Path) -> None:
    content, images = tasks_module._collect_mineru_assets(str(mineru_folder))
    assert "hello world" in content
    assert any(Path(p).name == "image1.jpg" for p in images)


@pytest.mark.asyncio
async def test_init_knowledge_base_if_needed_skips_when_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_check(_: str) -> bool:
        return True

    monkeypatch.setattr(tasks_module._qdrant_manager, "check_collection_exists", fake_check)
    monkeypatch.setattr(
        tasks_module._qdrant_manager,
        "get_collection_info",
        lambda: SimpleNamespace(vectors_count=1),
    )
    called: Dict[str, Any] = {"init": False}

    async def fake_init(_: str) -> None:
        called["init"] = True

    monkeypatch.setattr(tasks_module, "initialize_knowledge_base", fake_init)
    result = await tasks_module.init_knowledge_base_if_needed()
    assert result is True
    assert called["init"] is False


@pytest.mark.asyncio
async def test_init_knowledge_base_if_needed_runs_init(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_check(_: str) -> bool:
        return False

    monkeypatch.setattr(tasks_module._qdrant_manager, "check_collection_exists", fake_check)
    called: Dict[str, Any] = {"init": False}

    async def fake_init(_: str) -> None:
        called["init"] = True

    monkeypatch.setattr(tasks_module, "initialize_knowledge_base", fake_init)
    result = await tasks_module.init_knowledge_base_if_needed()
    assert result is True
    assert called["init"] is True


def test_process_pdf_task(monkeypatch: pytest.MonkeyPatch) -> None:
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

    def fake_acquisition(pg: Any, ptid: str, fps: List[str], nt: Dict[str, str]) -> Any:
        nt["acquisition"] = "success"
        return fps, nt

    async def fake_parsing(pg: Any, ptid: str, fps: List[str], nt: Dict[str, str]) -> Any:
        nt["parsing"] = "success"
        return _make_parsing_result("/tmp/mineru-output"), nt

    def fake_translation(pg: Any, ptid: str, md: str, nt: Dict[str, str]) -> Any:
        nt["translation"] = "success"
        return md, "en text", nt, []

    def fake_extraction(
        pg: Any,
        ptid: str,
        source: str,
        en: str,
        imgs: List[str],
        nt: Dict[str, str],
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

    monkeypatch.setattr(tasks_module, "run_node_acquisition", fake_acquisition)
    monkeypatch.setattr(tasks_module, "run_node_parsing", fake_parsing)
    monkeypatch.setattr(tasks_module, "run_node_translation", fake_translation)
    monkeypatch.setattr(tasks_module, "run_node_extraction", fake_extraction)
    monkeypatch.setattr(tasks_module, "run_node_acmg", fake_acmg)
    monkeypatch.setattr(tasks_module, "_store_outputs_in_minio", fake_store)
    monkeypatch.setattr(tasks_module, "_store_parsing_artifacts_in_minio", fake_store_parsing)
    monkeypatch.setattr(
        tasks_module.file_utils,
        "cleanup_old_temp_folders",
        lambda *_, **__: None,
    )

    result = _invoke_bound_task(tasks_module.process_pdf_task, ["file.pdf"])
    assert result["document_id"]
    assert result["graph_sync_result"] == {"pg_evidence_id": 1, "neo4j_synced": True}


def test_process_pdf_task_cleans_managed_temp_dir_on_success(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    evidence = _make_evidence_output(ps3_evidence={"ok": True})
    temp_file = _make_managed_upload_file(tmp_path)
    temp_dir = Path(temp_file).parent

    def fake_acquisition(pg: Any, ptid: str, fps: List[str], nt: Dict[str, str]) -> Any:
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
        return PipelineFiles(
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

    async def fake_store_parsing(*_: Any, **__: Any) -> DocumentParsingArtifact:
        return DocumentParsingArtifact(
            markdown_object_key="doc-1/parsing/parsed_markdown.md",
            markdown_url="/api/v1/results/doc-1/doc-1/parsing/parsed_markdown.md",
            image_object_keys=[],
        )

    monkeypatch.setattr(tasks_module, "run_node_acquisition", fake_acquisition)
    monkeypatch.setattr(tasks_module, "run_node_parsing", fake_parsing)
    monkeypatch.setattr(tasks_module, "run_node_translation", fake_translation)
    monkeypatch.setattr(tasks_module, "run_node_extraction", fake_extraction)
    monkeypatch.setattr(tasks_module, "run_node_acmg", fake_acmg)
    monkeypatch.setattr(tasks_module, "_store_outputs_in_minio", fake_store)
    monkeypatch.setattr(tasks_module, "_store_parsing_artifacts_in_minio", fake_store_parsing)
    monkeypatch.setattr(tasks_module.file_utils, "cleanup_old_temp_folders", lambda *_, **__: None)

    _invoke_bound_task(tasks_module.process_pdf_task, [temp_file])

    assert not temp_dir.exists()


def test_process_pdf_task_cleans_managed_temp_dir_on_final_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    temp_file = _make_managed_upload_file(tmp_path)
    temp_dir = Path(temp_file).parent

    def fake_acquisition(pg: Any, ptid: str, fps: List[str], nt: Dict[str, str]) -> Any:
        nt["acquisition"] = "success"
        return fps, nt

    async def fake_parsing(pg: Any, ptid: str, fps: List[str], nt: Dict[str, str]) -> Any:
        raise exc.ParsingException("parse failed")

    monkeypatch.setattr(tasks_module, "run_node_acquisition", fake_acquisition)
    monkeypatch.setattr(tasks_module, "run_node_parsing", fake_parsing)
    monkeypatch.setattr(tasks_module.file_utils, "cleanup_old_temp_folders", lambda *_, **__: None)
    setattr(tasks_module.process_pdf_task, "max_retries", 0)

    with pytest.raises(exc.ParsingException):
        _invoke_bound_task(tasks_module.process_pdf_task, [temp_file])

    assert not temp_dir.exists()


def test_process_pdf_task_origin_md_uses_source_text(monkeypatch: pytest.MonkeyPatch) -> None:
    source_md = "这是中文原文。"
    translated_md = "This is English translation."
    captured: Dict[str, Any] = {}

    class FakeAgent:
        def process_medical_evidence(
            self,
            markdown_content: str,
            image_paths: List[str],
            translated_md: str = "",
        ) -> EvidenceOutput:
            output = _make_evidence_output(ps3_evidence={"ok": True})
            output.origin_format_md = markdown_content
            output.en_format_md = translated_md
            output.status = "success"
            return output

    class FakePostgres:
        def append_paper_task_log(self, *_: Any, **__: Any) -> None:
            return None

    def fake_acquisition(pg: Any, ptid: str, fps: List[str], nt: Dict[str, str]) -> Any:
        nt["acquisition"] = "success"
        return fps, nt

    async def fake_parsing(pg: Any, ptid: str, fps: List[str], nt: Dict[str, str]) -> Any:
        nt["parsing"] = "success"
        return DocumentParsingResult(
            markdown_content=source_md,
            image_paths=[],
            mineru_folder="/tmp/mineru-output",
            parser_backend="mineru",
            parser_task_id="mineru-task-1",
            image_count=0,
            artifacts=DocumentParsingArtifact(
                markdown_object_key="doc-1/parsing/parsed_markdown.md",
                markdown_url="/api/v1/results/doc-1/doc-1/parsing/parsed_markdown.md",
                image_object_keys=[],
            ),
        ), nt

    def fake_translation(pg: Any, ptid: str, md: str, nt: Dict[str, str]) -> Any:
        nt["translation"] = "success"
        return source_md, translated_md, nt, []

    def fake_acmg(pg: Any, ptid: str, did: str, resp: Any, nt: Dict[str, str]) -> Any:
        nt["acmg"] = "success"
        return {"neo4j_synced": True}, nt

    async def fake_store(
        agent_response: EvidenceOutput,
        origin_image_paths: List[str],
        document_id: str,
    ) -> PipelineFiles:
        captured["origin_format_md"] = agent_response.origin_format_md
        captured["en_format_md"] = agent_response.en_format_md
        return PipelineFiles(
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

    async def fake_store_parsing(*_: Any, **__: Any) -> DocumentParsingArtifact:
        return DocumentParsingArtifact(
            markdown_object_key="doc-1/parsing/parsed_markdown.md",
            markdown_url="/api/v1/results/doc-1/doc-1/parsing/parsed_markdown.md",
            image_object_keys=[],
        )

    async def fake_init_kb() -> bool:
        return True

    monkeypatch.setattr(tasks_module, "_agents", FakeAgent())
    monkeypatch.setattr(tasks_module, "get_postgres_client", lambda: FakePostgres())
    monkeypatch.setattr(tasks_module, "run_node_acquisition", fake_acquisition)
    monkeypatch.setattr(tasks_module, "run_node_parsing", fake_parsing)
    monkeypatch.setattr(tasks_module, "run_node_translation", fake_translation)
    monkeypatch.setattr(tasks_module, "run_node_acmg", fake_acmg)
    monkeypatch.setattr(tasks_module, "_store_outputs_in_minio", fake_store)
    monkeypatch.setattr(tasks_module, "_store_parsing_artifacts_in_minio", fake_store_parsing)
    monkeypatch.setattr(tasks_module, "init_knowledge_base_if_needed", fake_init_kb)
    monkeypatch.setattr(
        tasks_module.file_utils,
        "cleanup_old_temp_folders",
        lambda *_, **__: None,
    )

    _invoke_bound_task(tasks_module.process_pdf_task, ["fake.pdf"])
    assert captured["origin_format_md"] == source_md
    assert captured["en_format_md"] == translated_md


def test_sync_evidence_to_graph_retries_transient_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class FlakySync:
        def __init__(self) -> None:
            self.calls = 0

        def sync_evidence(self, document_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
            self.calls += 1
            if self.calls < 2:
                raise RuntimeError("temporary failure")
            return {"pg_evidence_id": 9, "neo4j_synced": True}

    flaky = FlakySync()
    monkeypatch.setattr(tasks_module, "get_graph_sync_service", lambda: flaky)
    result = tasks_module._sync_evidence_to_graph("doc-1", {"any": "payload"})
    assert result == {"pg_evidence_id": 9, "neo4j_synced": True}
    assert flaky.calls == 2


def test_sync_evidence_to_graph_schema_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class BrokenSync:
        def sync_evidence(self, document_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
            raise SchemaSyncError("missing column", context={"document_id": document_id})

    monkeypatch.setattr(tasks_module, "get_graph_sync_service", lambda: BrokenSync())
    result = tasks_module._sync_evidence_to_graph("doc-99", {"ok": True})
    assert result is not None
    assert result["error_category"] == "schema"
    assert result["context"]["document_id"] == "doc-99"


def test_sync_evidence_to_graph_schedules_quality_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    class RetrySync:
        def sync_evidence(self, *_: Any, **__: Any) -> Dict[str, Any]:
            return {
                "pg_evidence_id": None,
                "neo4j_synced": False,
                "skipped": True,
                "retryable": True,
                "reason": "missing_core_fields",
                "context": {},
            }

    scheduled: Dict[str, Any] = {}

    def fake_schedule(doc_id: str, payload: Dict[str, Any], reason: str) -> None:
        scheduled["doc_id"] = doc_id
        scheduled["payload"] = payload
        scheduled["reason"] = reason

    monkeypatch.setattr(tasks_module, "get_graph_sync_service", lambda: RetrySync())
    monkeypatch.setattr(tasks_module, "_schedule_evidence_retry", fake_schedule)
    result = tasks_module._sync_evidence_to_graph("doc-2", {"foo": "bar"})
    assert result is not None
    assert result["skipped"] is True
    assert scheduled["doc_id"] == "doc-2"
    assert scheduled["reason"] == "missing_core_fields"
    assert scheduled["payload"]["foo"] == "bar"


def test_build_sentence_alignments_and_warning_detection() -> None:
    source = "NM_000527.4:c.123A>G\nsecond line"
    en = "translation line 1\nsecond line"
    aligns = tasks_module._build_sentence_alignments(source, en)
    assert len(aligns) == 2
    assert aligns[0]["source_sentence"] == "NM_000527.4:c.123A>G"
    warnings = tasks_module._detect_warning_codes(source, en)
    assert "HGVS_AUTOCORRECT_FAILED" in warnings


def test_persist_alignments_and_warnings_calls_postgres() -> None:
    class FakePostgres:
        def __init__(self) -> None:
            self.rows: List[Dict[str, Any]] = []

        def create_sentence_alignment(self, **kwargs: Any) -> Any:
            self.rows.append(kwargs)
            return None

    fake_pg = FakePostgres()
    warnings = tasks_module._persist_alignments_and_warnings(
        fake_pg,
        paper_task_id="paper-1",
        source_text="line1\nline2",
        en_text="en1\nen2",
        base_warnings=["FULLTEXT_UNAVAILABLE"],
    )
    assert len(fake_pg.rows) == 2
    assert fake_pg.rows[0]["paper_task_id"] == "paper-1"
    assert warnings == ["FULLTEXT_UNAVAILABLE"]


def test_get_node_policy_uses_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tasks_module.cfg, "node_extraction_max_retries", 5)
    monkeypatch.setattr(tasks_module.cfg, "node_extraction_delay_seconds", 7)
    monkeypatch.setattr(tasks_module.cfg, "node_extraction_timeout_seconds", 42)
    policy = tasks_module._get_node_policy("extraction")
    assert policy == {"max_retries": 5, "delay": 7, "timeout": 42}


@pytest.mark.asyncio
async def test_run_async_with_node_policy_retries_then_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tasks_module.cfg, "node_acquisition_max_retries", 2)
    monkeypatch.setattr(tasks_module.cfg, "node_acquisition_delay_seconds", 0)
    monkeypatch.setattr(tasks_module.cfg, "node_acquisition_timeout_seconds", 3)
    attempts = {"count": 0}

    async def flaky_runner() -> str:
        attempts["count"] += 1
        if attempts["count"] < 2:
            raise RuntimeError("temporary")
        return "ok"

    result, used_attempt = await tasks_module._run_async_with_node_policy(
        "acquisition",
        "test-op",
        flaky_runner,
    )
    assert result == "ok"
    assert used_attempt == 2


def test_process_pubmed_paper_task_success(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakePubMedService:
        async def fetch_article_metadata_abstract(self, pmid: str) -> Any:
            return SimpleNamespace(
                pmid=pmid,
                title="LDLR study",
                journal="Journal",
                pub_date="2025",
                abstract="Functional assay supports pathogenicity",
            )

    class FakeAgent:
        def process_medical_evidence(
            self, markdown_content: str, image_paths: List[str], translated_md: str = ""
        ) -> EvidenceOutput:
            assert "LDLR study" in markdown_content
            assert image_paths == []
            output = _make_evidence_output(ps3_evidence={"ok": True})
            output.en_format_md = translated_md or "LDLR translated abstract"
            return output

    class FakePostgres:
        def __init__(self) -> None:
            self.paper_updates: List[Dict[str, Any]] = []
            self.logs: List[Dict[str, Any]] = []
            self.documents: List[Dict[str, Any]] = []
            self.alignments: List[Dict[str, Any]] = []

        def update_paper_task(self, paper_task_id: str, **fields: Any) -> Any:
            self.paper_updates.append({"paper_task_id": paper_task_id, "fields": fields})
            return None

        def update_task_request(self, *_: Any, **__: Any) -> Any:
            return None

        def append_paper_task_log(self, paper_task_id: str, **kwargs: Any) -> Any:
            self.logs.append({"paper_task_id": paper_task_id, **kwargs})
            return None

        def update_document(self, document_id: str, **fields: Any) -> Any:
            self.documents.append({"document_id": document_id, "fields": fields})
            return None

        def refresh_task_request_status(self, _: str) -> Any:
            return None

        def create_sentence_alignment(self, **kwargs: Any) -> Any:
            self.alignments.append(kwargs)
            return None

    async def fake_store_outputs(*_: Any, **__: Any) -> PipelineFiles:
        return PipelineFiles(
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

    fake_pg = FakePostgres()
    monkeypatch.setattr(tasks_module, "get_postgres_client", lambda: fake_pg)
    monkeypatch.setattr(tasks_module, "get_pubmed_service", lambda: FakePubMedService())
    monkeypatch.setattr(tasks_module, "_agents", FakeAgent())
    monkeypatch.setattr(tasks_module, "_store_outputs_in_minio", fake_store_outputs)
    monkeypatch.setattr(tasks_module, "_sync_evidence_to_graph", lambda *_: {"neo4j_synced": True})

    result = _invoke_bound_task(
        tasks_module.process_pubmed_paper_task,
        pmid="12345678",
        document_id="doc-1",
        paper_task_id="paper-1",
        request_id="req-1",
    )

    assert result["status"] == "success"
    assert result["fulltext_unavailable"] is True
    assert fake_pg.paper_updates[-1]["fields"]["status"] == "success"
    assert "warning_codes" in fake_pg.paper_updates[-1]["fields"]
    assert "FULLTEXT_UNAVAILABLE" in fake_pg.paper_updates[-1]["fields"]["warning_codes"]
    assert len(fake_pg.alignments) >= 1
    assert any(log.get("node") == "acmg" for log in fake_pg.logs)


def test_process_pubmed_paper_task_fetch_timeout_marks_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakePubMedService:
        async def fetch_article_metadata_abstract(self, _: str) -> Any:
            raise RuntimeError("timeout")

    class FakePostgres:
        def __init__(self) -> None:
            self.paper_updates: List[Dict[str, Any]] = []
            self.logs: List[Dict[str, Any]] = []

        def update_paper_task(self, paper_task_id: str, **fields: Any) -> Any:
            self.paper_updates.append({"paper_task_id": paper_task_id, "fields": fields})
            return None

        def update_task_request(self, *_: Any, **__: Any) -> Any:
            return None

        def append_paper_task_log(self, paper_task_id: str, **kwargs: Any) -> Any:
            self.logs.append({"paper_task_id": paper_task_id, **kwargs})
            return None

        def refresh_task_request_status(self, _: str) -> Any:
            return None

    fake_pg = FakePostgres()
    monkeypatch.setattr(tasks_module, "get_postgres_client", lambda: fake_pg)
    monkeypatch.setattr(tasks_module, "get_pubmed_service", lambda: FakePubMedService())

    setattr(tasks_module.process_pubmed_paper_task, "max_retries", 0)

    with pytest.raises(RuntimeError):
        _invoke_bound_task(
            tasks_module.process_pubmed_paper_task,
            pmid="12345678",
            document_id="doc-1",
            paper_task_id="paper-1",
            request_id="req-1",
        )

    assert fake_pg.paper_updates[-1]["fields"]["status"] == "failed"
    assert fake_pg.paper_updates[-1]["fields"]["error_code"] == "FETCH_TIMEOUT"


def test_process_web_page_task_success(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeFirecrawlService:
        async def scrape_markdown(self, url: str) -> Any:
            return SimpleNamespace(
                source_url=url,
                final_url=url,
                title="LDLR web study",
                markdown="# LDLR web study\n\nFunctional assay supports pathogenicity.",
                metadata={"content_type": "text/html", "provider": "firecrawl"},
            )

    class FakeAgent:
        def process_medical_evidence(
            self, markdown_content: str, image_paths: List[str], translated_md: str = ""
        ) -> EvidenceOutput:
            assert "LDLR web study" in markdown_content
            assert image_paths == []
            output = _make_evidence_output(ps3_evidence={"ok": True})
            output.en_format_md = translated_md or "Translated LDLR web study"
            return output

    class FakePostgres:
        def __init__(self) -> None:
            self.paper_updates: List[Dict[str, Any]] = []
            self.logs: List[Dict[str, Any]] = []
            self.documents: List[Dict[str, Any]] = []
            self.alignments: List[Dict[str, Any]] = []

        def update_paper_task(self, paper_task_id: str, **fields: Any) -> Any:
            self.paper_updates.append({"paper_task_id": paper_task_id, "fields": fields})
            return None

        def update_task_request(self, *_: Any, **__: Any) -> Any:
            return None

        def append_paper_task_log(self, paper_task_id: str, **kwargs: Any) -> Any:
            self.logs.append({"paper_task_id": paper_task_id, **kwargs})
            return None

        def update_document(self, document_id: str, **fields: Any) -> Any:
            self.documents.append({"document_id": document_id, "fields": fields})
            return None

        def refresh_task_request_status(self, _: str) -> Any:
            return None

        def create_sentence_alignment(self, **kwargs: Any) -> Any:
            self.alignments.append(kwargs)
            return None

    async def fake_store_outputs(*_: Any, **__: Any) -> PipelineFiles:
        return PipelineFiles(
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

    async def fake_store_acquired_web_content(*_: Any, **__: Any) -> str:
        return "literature/web/ldlr-web-study.md"

    fake_pg = FakePostgres()
    monkeypatch.setattr(tasks_module, "get_postgres_client", lambda: fake_pg)
    monkeypatch.setattr(tasks_module, "get_firecrawl_service", lambda: FakeFirecrawlService())
    monkeypatch.setattr(tasks_module, "_agents", FakeAgent())
    monkeypatch.setattr(tasks_module, "_store_outputs_in_minio", fake_store_outputs)
    monkeypatch.setattr(
        tasks_module, "_store_acquired_web_content", fake_store_acquired_web_content
    )
    monkeypatch.setattr(tasks_module, "_sync_evidence_to_graph", lambda *_: {"neo4j_synced": True})

    result = _invoke_bound_task(
        tasks_module.process_web_page_task,
        url="https://example.org/ldlr-web-study",
        document_id="doc-1",
        paper_task_id="paper-1",
        request_id="req-1",
    )

    assert result["status"] == "success"
    assert result["source_url"] == "https://example.org/ldlr-web-study"
    assert fake_pg.paper_updates[-1]["fields"]["status"] == "success"
    assert any(
        item["fields"].get("workflow_status") == "COMPLETED" for item in fake_pg.paper_updates
    )
    assert any(
        item["fields"].get("local_path") == "literature/web/ldlr-web-study.md"
        for item in fake_pg.documents
    )
    assert any(log.get("node") == "acmg" for log in fake_pg.logs)


# ---------------------------------------------------------------------------
# M1 utility helpers
# ---------------------------------------------------------------------------


class _FakePostgresForNodes:
    """Minimal postgres stub that records ``append_paper_task_log`` calls."""

    def __init__(self) -> None:
        self.logs: List[Dict[str, Any]] = []

    def append_paper_task_log(self, paper_task_id: str, **kwargs: Any) -> None:
        self.logs.append({"paper_task_id": paper_task_id, **kwargs})


def test_log_node_start_skips_when_task_id_empty() -> None:
    fake_pg = _FakePostgresForNodes()
    tasks_module._log_node_start(fake_pg, "", "acmg")
    assert fake_pg.logs == []


def test_log_node_end_skips_when_task_id_empty() -> None:
    fake_pg = _FakePostgresForNodes()
    tasks_module._log_node_end(fake_pg, "", "acmg", success=True)
    assert fake_pg.logs == []


def test_detect_language_english() -> None:
    text = (
        "The LDLR gene encodes the low-density lipoprotein receptor. "
        "Mutations in this gene cause familial hypercholesterolemia."
    )
    assert tasks_module._detect_language(text) == "en"


def test_detect_language_chinese() -> None:
    text = "这是一段中文文本，用于测试语言检测功能。该段落包含大量中文字符以确保准确。"
    assert tasks_module._detect_language(text) == "unknown"


def test_detect_language_empty() -> None:
    assert tasks_module._detect_language("") == "unknown"
    assert tasks_module._detect_language("   ") == "unknown"


def test_is_docx_true() -> None:
    assert tasks_module._is_docx("report.docx") is True
    assert tasks_module._is_docx("report.DOC") is True
    assert tasks_module._is_docx("/some/path/file.DOCX") is True


def test_is_docx_false() -> None:
    assert tasks_module._is_docx("report.pdf") is False
    assert tasks_module._is_docx("file.txt") is False
    assert tasks_module._is_docx("data.xlsx") is False


def test_attempt_hgvs_correction_no_missing() -> None:
    source = "Variant NM_000527.4:c.123A>G was found."
    translated = "The variant NM_000527.4:c.123A>G was identified."
    result, all_restored = tasks_module._attempt_hgvs_correction(source, translated)
    assert all_restored is True
    assert result == translated


def test_attempt_hgvs_correction_with_prefix_match() -> None:
    source = "Variant NM_000527.4:c.123A>G was found."
    translated = "The variant NM_000truncated was identified."
    result, all_restored = tasks_module._attempt_hgvs_correction(source, translated)
    assert "c.123A>G" in result
    assert all_restored is True


def test_attempt_hgvs_correction_fallback_append() -> None:
    source = "Variant NM_000527.4:c.123A>G was found."
    translated = "The variant was completely removed from the translation."
    result, all_restored = tasks_module._attempt_hgvs_correction(source, translated)
    assert all_restored is False
    assert "[HGVS Reference]" in result
    assert "c.123A>G" in result


def test_run_node_acquisition_success(tmp_path: Path) -> None:
    fake_pg = _FakePostgresForNodes()
    temp_file = tmp_path / "test.pdf"
    temp_file.write_bytes(b"fake pdf content")
    paths = [str(temp_file)]
    node_trace: Dict[str, str] = {}

    result_paths, result_trace = tasks_module.run_node_acquisition(
        fake_pg, "paper-1", paths, node_trace
    )
    assert result_paths == paths
    assert result_trace["acquisition"] == "success"
    assert len(fake_pg.logs) == 2


def test_run_node_acquisition_missing_file() -> None:
    fake_pg = _FakePostgresForNodes()
    node_trace: Dict[str, str] = {}

    with pytest.raises(exc.ValidationException):
        tasks_module.run_node_acquisition(fake_pg, "paper-1", ["/nonexistent/file.pdf"], node_trace)
    assert len(fake_pg.logs) == 2
    assert fake_pg.logs[1].get("error_code") == "INPUT_INVALID"


@pytest.mark.asyncio
async def test_run_node_parsing_docx_terminal() -> None:
    fake_pg = _FakePostgresForNodes()
    node_trace: Dict[str, str] = {}

    with pytest.raises(exc.ParsingException, match="DOCX"):
        await tasks_module.run_node_parsing(fake_pg, "paper-1", ["report.docx"], node_trace)
    assert fake_pg.logs[1].get("error_code") == "PARSE_FAILED"


@pytest.mark.asyncio
async def test_run_node_parsing_returns_structured_result(
    monkeypatch: pytest.MonkeyPatch, mineru_folder: Path
) -> None:
    fake_pg = _FakePostgresForNodes()
    node_trace: Dict[str, str] = {}

    async def fake_run_async_with_policy(*_: Any, **__: Any) -> Any:
        parsing_result = _make_parsing_result(str(mineru_folder))
        parsing_result.markdown_content = "hello world"
        parsing_result.image_paths = [str(mineru_folder / "image1.jpg")]
        parsing_result.image_count = 1
        return parsing_result, 1

    monkeypatch.setattr(tasks_module, "_run_async_with_node_policy", fake_run_async_with_policy)

    parsing_result, result_trace = await tasks_module.run_node_parsing(
        fake_pg,
        "paper-1",
        ["paper.pdf"],
        node_trace,
    )

    assert parsing_result.markdown_content == "hello world"
    assert parsing_result.mineru_folder == str(mineru_folder)
    assert parsing_result.parser_backend == "mineru"
    assert parsing_result.parser_task_id == "mineru-task-1"
    assert parsing_result.image_paths
    assert result_trace["parsing"] == "success"


def test_process_pdf_task_persists_parsing_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    evidence = _make_evidence_output(ps3_evidence={"ok": True})
    parsing_result = _make_parsing_result("/tmp/mineru-output")

    def fake_acquisition(pg: Any, ptid: str, fps: List[str], nt: Dict[str, str]) -> Any:
        nt["acquisition"] = "success"
        return fps, nt

    async def fake_parsing(pg: Any, ptid: str, fps: List[str], nt: Dict[str, str]) -> Any:
        nt["parsing"] = "success"
        return parsing_result, nt

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

    async def fake_store_outputs(*_: Any, **__: Any) -> PipelineFiles:
        return PipelineFiles(
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

    async def fake_store_parsing(*_: Any, **__: Any) -> DocumentParsingArtifact:
        return parsing_result.artifacts

    monkeypatch.setattr(tasks_module, "run_node_acquisition", fake_acquisition)
    monkeypatch.setattr(tasks_module, "run_node_parsing", fake_parsing)
    monkeypatch.setattr(tasks_module, "run_node_translation", fake_translation)
    monkeypatch.setattr(tasks_module, "run_node_extraction", fake_extraction)
    monkeypatch.setattr(tasks_module, "run_node_acmg", fake_acmg)
    monkeypatch.setattr(tasks_module, "_store_outputs_in_minio", fake_store_outputs)
    monkeypatch.setattr(
        tasks_module,
        "_store_parsing_artifacts_in_minio",
        fake_store_parsing,
        raising=False,
    )
    monkeypatch.setattr(tasks_module.file_utils, "cleanup_old_temp_folders", lambda *_, **__: None)

    result = _invoke_bound_task(tasks_module.process_pdf_task, ["file.pdf"])
    assert result["mineru_folder"] == "/tmp/mineru-output"
    assert result["parsing_metadata"]["parser_backend"] == "mineru"
    assert result["parsing_metadata"]["parser_task_id"] == "mineru-task-1"


def test_process_pdf_task_parsing_artifacts_saved_before_extraction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence = _make_evidence_output(ps3_evidence={"ok": True})
    parsing_result = _make_parsing_result("/tmp/mineru-output")
    events: List[str] = []

    def fake_acquisition(pg: Any, ptid: str, fps: List[str], nt: Dict[str, str]) -> Any:
        nt["acquisition"] = "success"
        return fps, nt

    async def fake_parsing(pg: Any, ptid: str, fps: List[str], nt: Dict[str, str]) -> Any:
        events.append("parsing")
        nt["parsing"] = "success"
        return parsing_result, nt

    async def fake_store_parsing(*_: Any, **__: Any) -> DocumentParsingArtifact:
        events.append("store_parsing")
        return parsing_result.artifacts

    def fake_translation(pg: Any, ptid: str, md: str, nt: Dict[str, str]) -> Any:
        nt["translation"] = "success"
        return md, "en text", nt, []

    def fake_extraction(
        pg: Any, ptid: str, source: str, en: str, imgs: List[str], nt: Dict[str, str]
    ) -> Any:
        assert events == ["parsing", "store_parsing"]
        nt["extraction"] = "success"
        return evidence, nt

    def fake_acmg(pg: Any, ptid: str, did: str, resp: Any, nt: Dict[str, str]) -> Any:
        nt["acmg"] = "success"
        return {"neo4j_synced": True}, nt

    async def fake_store_outputs(*_: Any, **__: Any) -> PipelineFiles:
        return PipelineFiles(
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

    monkeypatch.setattr(tasks_module, "run_node_acquisition", fake_acquisition)
    monkeypatch.setattr(tasks_module, "run_node_parsing", fake_parsing)
    monkeypatch.setattr(tasks_module, "run_node_translation", fake_translation)
    monkeypatch.setattr(tasks_module, "run_node_extraction", fake_extraction)
    monkeypatch.setattr(tasks_module, "run_node_acmg", fake_acmg)
    monkeypatch.setattr(tasks_module, "_store_outputs_in_minio", fake_store_outputs)
    monkeypatch.setattr(
        tasks_module,
        "_store_parsing_artifacts_in_minio",
        fake_store_parsing,
        raising=False,
    )
    monkeypatch.setattr(tasks_module.file_utils, "cleanup_old_temp_folders", lambda *_, **__: None)

    _invoke_bound_task(tasks_module.process_pdf_task, ["file.pdf"])


def test_run_node_translation_english_skip() -> None:
    fake_pg = _FakePostgresForNodes()
    node_trace: Dict[str, str] = {}
    english_text = (
        "The BRCA1 gene is associated with hereditary breast cancer. "
        "Pathogenic variants in BRCA1 increase lifetime risk significantly. "
        "Functional assays demonstrate loss of protein activity."
    )

    source_text, en_text, result_trace, warnings = tasks_module.run_node_translation(
        fake_pg, "paper-1", english_text, node_trace
    )
    assert source_text == english_text
    assert en_text == english_text
    assert result_trace["translation"] == "skipped_english"
    assert warnings == []


def test_paddleocr_available_false() -> None:
    from src.domain.mineru.component import paddleocr_available

    assert paddleocr_available() is False
