from __future__ import annotations

from typing import Any, cast

import pytest

from src.domain.literature import (
    LiteratureAcquisitionAgent as LegacyLiteratureAcquisitionAgent,
)
from src.domain.literature import get_firecrawl_service as legacy_get_firecrawl_service
from src.domain.literature import get_pubmed_service as legacy_get_pubmed_service
from src.domain.literature.acquisition_agent import AcquisitionPlanItem
from src.services.enum import default_processing_steps
from src.state.global_state import SupervisorState
from src.utils.exceptions import ValidationException


def test_acquisition_wrapper_imports_and_legacy_compatibility() -> None:
    from src.agents.acquisition import (
        LiteratureAcquisitionAgent,
        get_firecrawl_service,
        get_pubmed_service,
        run_acquisition_node,
    )

    assert LiteratureAcquisitionAgent is LegacyLiteratureAcquisitionAgent
    assert get_firecrawl_service is legacy_get_firecrawl_service
    assert get_pubmed_service is legacy_get_pubmed_service
    assert callable(run_acquisition_node)


def test_run_acquisition_node_upload_marks_success(tmp_path) -> None:
    from src.agents.acquisition import run_acquisition_node

    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_text("synthetic")

    state = cast(
        SupervisorState,
        cast(
            object,
            {
                "source": "upload",
                "file_paths": [str(pdf_path)],
                "node_trace": {},
                "processing_steps": default_processing_steps(),
            },
        ),
    )

    result = run_acquisition_node(state)

    assert result["current_node"] == "acquisition"
    assert result["node_trace"]["acquisition"] == "success"
    assert result["node_trace"]["acquisition_detail"] == {
        "source": "upload",
        "count": 1,
        "items": [{"file_path": str(pdf_path)}],
    }
    assert result["processing_steps"]["acquisition"]["status"] == "COMPLETED"
    assert result["file_paths"] == [str(pdf_path)]


def test_run_acquisition_node_upload_raises_for_missing_files() -> None:
    from src.agents.acquisition import run_acquisition_node

    with pytest.raises(ValidationException, match="Files not found"):
        run_acquisition_node(
            cast(
                SupervisorState,
                cast(object, {"source": "upload", "file_paths": ["/tmp/missing.pdf"]}),
            )
        )


def test_run_acquisition_node_upload_does_not_instantiate_planner(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    from src.agents.acquisition import node as acquisition_node

    pdf_path = tmp_path / "upload.pdf"
    pdf_path.write_text("synthetic")

    monkeypatch.setattr(
        acquisition_node,
        "get_literature_acquisition_agent",
        lambda: (_ for _ in ()).throw(AssertionError("planner should not be used")),
    )

    result = acquisition_node.run_acquisition_node(
        cast(
            SupervisorState,
            cast(
                object,
                {
                    "source": "upload",
                    "file_paths": [str(pdf_path)],
                    "node_trace": {},
                    "processing_steps": default_processing_steps(),
                },
            ),
        )
    )

    assert result["current_node"] == "acquisition"
    assert result["processing_steps"]["acquisition"]["status"] == "COMPLETED"
    assert "acquisition_plan" not in result


def test_run_acquisition_node_pubmed_maps_plan(monkeypatch) -> None:
    from src.agents.acquisition import node as acquisition_node

    class FakeAcquisitionAgent:
        def plan_pubmed_request(self, pmids: list[str]) -> list[AcquisitionPlanItem]:
            assert pmids == ["12345"]
            return [
                AcquisitionPlanItem(
                    source="pubmed",
                    raw_value="12345",
                    normalized_value="12345",
                    fingerprint="pmid:12345",
                    display_name="PMID:12345",
                    metadata={"pmid": "12345"},
                )
            ]

    monkeypatch.setattr(
        acquisition_node,
        "get_literature_acquisition_agent",
        lambda: FakeAcquisitionAgent(),
    )
    async def fake_workflow(payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "success": True,
            "items": [{"title": "PMC article"}],
            "downloads": [],
            "warnings": [],
            "route": {"used": "api", "api_provider": "pmc"},
            "raw": {
                "api": {
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
                    ]
                }
            },
        }

    monkeypatch.setattr(
        acquisition_node,
        "literature_unified_workflow",
        fake_workflow,
        raising=False,
    )

    state = cast(
        SupervisorState,
        cast(
            object,
            {
                "source": "pubmed",
                "pmids": ["12345"],
                "node_trace": {},
                "processing_steps": default_processing_steps(),
            },
        ),
    )

    result = acquisition_node.run_acquisition_node(state)
    result_dict = cast(dict[str, Any], cast(object, result))
    acquisition_plan = result_dict["acquisition_plan"]

    assert isinstance(acquisition_plan, list)

    assert result["current_node"] == "acquisition"
    assert result["pmids"] == ["12345"]
    assert acquisition_plan[0]["fingerprint"] == "pmid:12345"
    assert result["node_trace"]["acquisition"] == "success"
    assert result["node_trace"]["acquisition_detail"] == {
        "source": "pubmed",
        "count": 1,
        "items": [
            {
                "source": "pubmed",
                "normalized_value": "12345",
                "fingerprint": "pmid:12345",
                "metadata": {"pmid": "12345"},
            }
        ],
    }
    assert result["acquisition_result"]["route"]["used"] == "api"
    assert result["node_trace"]["acquisition_result"]["route"]["api_provider"] == "pmc"
    assert result["processing_steps"]["acquisition"]["status"] == "COMPLETED"


def test_run_acquisition_node_web_invokes_unified_workflow(monkeypatch) -> None:
    from src.agents.acquisition import node as acquisition_node

    class FakeAcquisitionAgent:
        def plan_web_request(self, urls: list[str]) -> list[AcquisitionPlanItem]:
            assert urls == ["https://cyberleninka.ru/article/n/test"]
            return [
                AcquisitionPlanItem(
                    source="web",
                    raw_value="https://cyberleninka.ru/article/n/test",
                    normalized_value="https://cyberleninka.ru/article/n/test",
                    fingerprint="url:fingerprint",
                    display_name="https://cyberleninka.ru/article/n/test",
                    metadata={
                        "source_url": "https://cyberleninka.ru/article/n/test",
                    },
                )
            ]

    async def fake_workflow(payload: dict[str, Any]) -> dict[str, Any]:
        assert payload["prefer"] == "web"
        assert payload["query"] == "https://cyberleninka.ru/article/n/test"
        return {
            "success": True,
            "items": [{"title": "Cyberleninka article"}],
            "downloads": [],
            "warnings": [],
            "route": {"used": "web", "web_provider": "cyberleninka"},
            "raw": {
                "web": {
                    "source_trace": [
                        {
                            "provider": "cyberleninka",
                            "attempt": 1,
                            "success": True,
                            "items_count": 1,
                            "downloads_count": 0,
                            "warnings": [],
                            "error": None,
                        }
                    ]
                }
            },
        }

    monkeypatch.setattr(
        acquisition_node,
        "get_literature_acquisition_agent",
        lambda: FakeAcquisitionAgent(),
    )
    monkeypatch.setattr(
        acquisition_node,
        "literature_unified_workflow",
        fake_workflow,
        raising=False,
    )

    state = cast(
        SupervisorState,
        cast(
            object,
            {
                "source": "web",
                "urls": ["https://cyberleninka.ru/article/n/test"],
                "node_trace": {},
                "processing_steps": default_processing_steps(),
            },
        ),
    )

    result = acquisition_node.run_acquisition_node(state)

    assert result["current_node"] == "acquisition"
    assert result["node_trace"]["acquisition"] == "success"
    assert result["node_trace"]["acquisition_result"]["route"]["used"] == "web"
    assert result["acquisition_result"]["route"]["web_provider"] == "cyberleninka"
    assert result["processing_steps"]["acquisition"]["status"] == "COMPLETED"


def test_run_acquisition_node_pubmed_download_sets_file_paths(monkeypatch) -> None:
    from src.agents.acquisition import node as acquisition_node

    class FakeAcquisitionAgent:
        def plan_pubmed_request(self, pmids: list[str]) -> list[AcquisitionPlanItem]:
            assert pmids == ["12345"]
            return [
                AcquisitionPlanItem(
                    source="pubmed",
                    raw_value="12345",
                    normalized_value="12345",
                    fingerprint="pmid:12345",
                    display_name="PMID:12345",
                    metadata={"pmid": "12345"},
                )
            ]

    async def fake_workflow(payload: dict[str, Any]) -> dict[str, Any]:
        assert payload["action"] == "download"
        return {
            "success": True,
            "items": [],
            "downloads": [{"file_path": "/tmp/paper.pdf"}],
            "warnings": [],
            "route": {"used": "api", "api_provider": "pmc"},
            "raw": {"api": {"source_trace": []}},
        }

    monkeypatch.setattr(
        acquisition_node,
        "get_literature_acquisition_agent",
        lambda: FakeAcquisitionAgent(),
    )
    monkeypatch.setattr(
        acquisition_node,
        "literature_unified_workflow",
        fake_workflow,
        raising=False,
    )

    state = cast(
        SupervisorState,
        cast(
            object,
            {
                "source": "pubmed",
                "pmids": ["12345"],
                "node_trace": {},
                "processing_steps": default_processing_steps(),
            },
        ),
    )

    result = acquisition_node.run_acquisition_node(state)

    assert result["file_paths"] == ["/tmp/paper.pdf"]
    assert result["acquisition_result"]["downloads"][0]["file_path"] == "/tmp/paper.pdf"


def test_run_acquisition_node_raises_when_unified_workflow_returns_no_result(
    monkeypatch,
) -> None:
    from src.agents.acquisition import node as acquisition_node

    class FakeAcquisitionAgent:
        def plan_web_request(self, urls: list[str]) -> list[AcquisitionPlanItem]:
            return [
                AcquisitionPlanItem(
                    source="web",
                    raw_value=urls[0],
                    normalized_value=urls[0],
                    fingerprint="url:fingerprint",
                    display_name=urls[0],
                    metadata={"source_url": urls[0]},
                )
            ]

    monkeypatch.setattr(
        acquisition_node,
        "get_literature_acquisition_agent",
        lambda: FakeAcquisitionAgent(),
    )
    async def fake_workflow(payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "success": False,
            "items": [],
            "downloads": [],
            "warnings": ["FETCH_NO_RESULT"],
            "route": {"used": "web", "reason": "web_no_items"},
        }

    monkeypatch.setattr(
        acquisition_node,
        "literature_unified_workflow",
        fake_workflow,
        raising=False,
    )

    state = cast(
        SupervisorState,
        cast(
            object,
            {
                "source": "web",
                "urls": ["https://cyberleninka.ru/article/n/test"],
                "node_trace": {},
                "processing_steps": default_processing_steps(),
            },
        ),
    )

    with pytest.raises(ValidationException, match="FETCH_NO_RESULT"):
        acquisition_node.run_acquisition_node(state)
