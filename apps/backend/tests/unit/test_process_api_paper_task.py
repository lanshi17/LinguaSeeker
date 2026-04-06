from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import pytest

from src.domain.models import DocumentParsingArtifact, DocumentParsingResult, EvidenceOutput, PipelineFiles
from src.services import task_manager as tasks_module


def _make_evidence_output() -> EvidenceOutput:
    return EvidenceOutput(
        ps3_evidence={"ok": True},
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


def test_process_api_paper_task_success_persists_source_trace_and_emits_kg_event(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "downloaded.pdf"
    pdf_path.write_bytes(b"%PDF-1.7 api")

    class FakePostgres:
        def __init__(self) -> None:
            self.paper_updates: List[Dict[str, Any]] = []
            self.logs: List[Dict[str, Any]] = []
            self.documents: List[Dict[str, Any]] = []

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

        def create_sentence_alignment(self, **_: Any) -> Any:
            return None

    class FakeKGEvents:
        def __init__(self) -> None:
            self.created: List[Dict[str, Any]] = []

        def create_kg_event(self, **kwargs: Any) -> Any:
            self.created.append(kwargs)
            return None

    async def fake_literature_unified_workflow(payload: Dict[str, Any]) -> Dict[str, Any]:
        assert payload["prefer"] == "api"
        assert payload["api_provider"] == "pmc"
        assert payload["action"] == "search"
        return {
            "success": True,
            "items": [
                {
                    "source": "pmc",
                    "title": "Functional analysis of BARD1",
                    "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC1234567/",
                    "identifiers": {"pmcid": "PMC1234567"},
                }
            ],
            "warnings": [],
            "raw": {
                "api": {
                    "items": [
                        {
                            "title": "Functional analysis of BARD1",
                            "abstract": "Functional assay supports pathogenicity.",
                        }
                    ],
                    "source_trace": [
                        {
                            "provider": "pmc",
                            "attempt": 1,
                            "success": True,
                            "items_count": 1,
                            "downloads_count": 0,
                            "warnings": [],
                            "error": None,
                        }
                    ],
                }
            },
        }

    async def fake_download(*_: Any, **__: Any) -> Dict[str, Any]:
        return {
            "downloaded": True,
            "provider": "pmc",
            "source_trace": [
                {
                    "provider": "pmc",
                    "attempt": 1,
                    "success": True,
                    "items_count": 1,
                    "downloads_count": 1,
                    "warnings": [],
                    "error": None,
                }
            ],
            "object_key": "literature/mock/object.pdf",
            "local_file_path": str(pdf_path),
        }

    async def fake_run_node_parsing(*_: Any, **__: Any) -> Any:
        return (
            DocumentParsingResult(
                markdown_content="parsed markdown",
                image_paths=["/tmp/image.jpg"],
                mineru_folder="/tmp/mineru",
                parser_backend="mineru",
                parser_task_id="parser-1",
                image_count=1,
                artifacts=DocumentParsingArtifact(
                    markdown_object_key="",
                    image_object_keys=[],
                ),
            ),
            {"acquisition": "success", "parsing": "success"},
        )

    async def fake_store_parsing_artifacts(*_: Any, **__: Any) -> DocumentParsingArtifact:
        return DocumentParsingArtifact(
            markdown_object_key="doc-1/parsing/parsed_markdown.md",
            markdown_url="/api/v1/results/doc-1/doc-1/parsing/parsed_markdown.md",
            image_object_keys=["doc-1/parsing/images/img.jpg"],
        )

    def fake_translation(*_: Any, **__: Any) -> Any:
        return "parsed markdown", "translated markdown", {"translation": "success"}, []

    def fake_extraction(*_: Any, **__: Any) -> Any:
        return _make_evidence_output(), {"extraction": "success"}

    def fake_acmg(*_: Any, **__: Any) -> Any:
        return {"neo4j_synced": True}, {"acmg": "success"}

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
    fake_kg_events = FakeKGEvents()
    monkeypatch.setattr(tasks_module, "get_postgres_client", lambda: fake_pg)
    monkeypatch.setattr(tasks_module, "literature_unified_workflow", fake_literature_unified_workflow)
    monkeypatch.setattr(tasks_module, "_try_download_and_store_literature_pdf", fake_download)
    monkeypatch.setattr(tasks_module, "run_node_parsing", fake_run_node_parsing)
    monkeypatch.setattr(tasks_module, "_store_parsing_artifacts_in_minio", fake_store_parsing_artifacts)
    monkeypatch.setattr(tasks_module, "run_node_translation", fake_translation)
    monkeypatch.setattr(tasks_module, "run_node_extraction", fake_extraction)
    monkeypatch.setattr(tasks_module, "run_node_acmg", fake_acmg)
    monkeypatch.setattr(tasks_module, "_store_outputs_in_minio", fake_store_outputs)
    monkeypatch.setattr(tasks_module, "get_kg_event_service", lambda: fake_kg_events, raising=False)

    result = tasks_module.process_api_paper_task(
        source="pmc",
        request_payload={
            "query": "BARD1 hereditary breast cancer",
            "identifiers": ["PMCID:PMC1234567"],
            "selected_title": "Functional analysis of BARD1",
            "detail_link": "https://pmc.ncbi.nlm.nih.gov/articles/PMC1234567/",
        },
        document_id="doc-1",
        paper_task_id="paper-1",
        request_id="req-1",
    )

    assert result["status"] == "success"
    assert result["trace_chain"]["steps"]["acquisition"]["outcome"] == "success"
    assert result["pdf_download"]["source_trace"][0]["provider"] == "pmc"
    assert fake_pg.paper_updates[-1]["fields"]["status"] == "success"
    assert fake_pg.paper_updates[-1]["fields"]["node_trace"]["acquisition_detail"]["provider"] == "pmc"
    assert fake_kg_events.created[0]["paper_task_id"] == "paper-1"


def test_process_api_paper_task_marks_fulltext_unavailable_when_only_metadata_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

        def update_document(self, *_: Any, **__: Any) -> Any:
            return None

        def refresh_task_request_status(self, _: str) -> Any:
            return None

        def create_sentence_alignment(self, **_: Any) -> Any:
            return None

    async def fake_literature_unified_workflow(payload: Dict[str, Any]) -> Dict[str, Any]:
        assert payload["action"] == "search"
        return {
            "success": True,
            "items": [
                {
                    "source": "crossref",
                    "title": "Open article",
                    "url": "https://example.org/open-article",
                    "identifiers": {"doi": "10.1000/example"},
                }
            ],
            "warnings": [],
            "raw": {
                "api": {
                    "items": [
                        {
                            "title": "Open article",
                            "abstract": "Metadata only evidence.",
                        }
                    ],
                    "source_trace": [
                        {
                            "provider": "crossref",
                            "attempt": 1,
                            "success": True,
                            "items_count": 1,
                            "downloads_count": 0,
                            "warnings": [],
                            "error": None,
                        }
                    ],
                }
            },
        }

    async def fake_download(*_: Any, **__: Any) -> Dict[str, Any]:
        return {
            "downloaded": False,
            "provider": "crossref",
            "source_trace": [
                {
                    "provider": "crossref",
                    "attempt": 1,
                    "success": True,
                    "items_count": 1,
                    "downloads_count": 0,
                    "warnings": ["FULLTEXT_UNAVAILABLE"],
                    "error": None,
                }
            ],
        }

    def fake_translation(*_: Any, **__: Any) -> Any:
        return "source text", "translated text", {"translation": "success"}, []

    def fake_extraction(*_: Any, **__: Any) -> Any:
        return _make_evidence_output(), {"extraction": "success"}

    def fake_acmg(*_: Any, **__: Any) -> Any:
        return {"neo4j_synced": True}, {"acmg": "success"}

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
    monkeypatch.setattr(tasks_module, "literature_unified_workflow", fake_literature_unified_workflow)
    monkeypatch.setattr(tasks_module, "_try_download_and_store_literature_pdf", fake_download)
    monkeypatch.setattr(tasks_module, "run_node_translation", fake_translation)
    monkeypatch.setattr(tasks_module, "run_node_extraction", fake_extraction)
    monkeypatch.setattr(tasks_module, "run_node_acmg", fake_acmg)
    monkeypatch.setattr(tasks_module, "_store_outputs_in_minio", fake_store_outputs)
    monkeypatch.setattr(tasks_module, "_emit_kg_event_for_success", lambda *_, **__: None)

    result = tasks_module.process_api_paper_task(
        source="crossref",
        request_payload={
            "query": "10.1000/example",
            "identifiers": ["DOI:10.1000/example"],
            "selected_title": "Open article",
            "detail_link": "https://example.org/open-article",
        },
        document_id="doc-1",
        paper_task_id="paper-1",
        request_id="req-1",
    )

    assert result["status"] == "success"
    assert result["fulltext_unavailable"] is True
    assert "FULLTEXT_UNAVAILABLE" in result["warning_codes"]
    assert fake_pg.paper_updates[-1]["fields"]["fulltext_unavailable"] is True
