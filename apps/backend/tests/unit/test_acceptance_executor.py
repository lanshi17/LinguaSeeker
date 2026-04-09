from __future__ import annotations

import pytest

import src.services.acceptance_executor as acceptance_executor
from src.services.acceptance_executor import enqueue_manifest_paper
from src.services.release_reporting import AcceptancePaperRecord
from src.services.dtos import PaperTaskItemResponse, TaskRequestCreateResponse


def test_enqueue_manifest_paper_dispatches_web_entries() -> None:
    paper = AcceptancePaperRecord.model_validate(
        {
            "paper_id": "web-001",
            "entry_kind": "web",
            "source": "web",
            "request_payload": {"urls": ["https://example.com/paper"]},
            "status": "queued",
        }
    )
    seen: list[str] = []

    def fake_web_dispatcher(entry: AcceptancePaperRecord) -> dict[str, str]:
        seen.append(entry.paper_id)
        return {"request_id": "req-1", "paper_task_id": "paper-1"}

    result = enqueue_manifest_paper(paper, dispatchers={"web": fake_web_dispatcher})

    assert seen == ["web-001"]
    assert result == {"request_id": "req-1", "paper_task_id": "paper-1"}


def test_enqueue_manifest_paper_requires_execution_metadata() -> None:
    paper = AcceptancePaperRecord.model_validate(
        {
            "paper_id": "api-001",
            "entry_kind": "api",
            "status": "queued",
        }
    )

    with pytest.raises(ValueError, match="request_payload"):
        enqueue_manifest_paper(paper, dispatchers={"api": lambda _: {}})


def test_enqueue_web_manifest_paper_calls_existing_web_flow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paper = AcceptancePaperRecord.model_validate(
        {
            "paper_id": "web-001",
            "entry_kind": "web",
            "source": "web",
            "request_payload": {
                "task_form": "{\"goal\":\"PS3 evidence\",\"disease\":\"FH\",\"country\":\"CN\",\"language\":\"EN\"}",
                "urls": ["https://example.com/paper"],
                "force_refresh": True,
            },
            "status": "queued",
        }
    )
    captured: dict[str, object] = {}

    def fake_create_task_request_by_web_crawl(payload: object) -> TaskRequestCreateResponse:
        captured["payload"] = payload
        return TaskRequestCreateResponse(
            request_id="req-web-1",
            status="queued",
            papers=[
                PaperTaskItemResponse(
                    paper_task_id="web-paper-1",
                    filename="paper.html",
                    status="queued",
                )
            ],
        )

    monkeypatch.setattr(
        acceptance_executor,
        "create_task_request_by_web_crawl",
        fake_create_task_request_by_web_crawl,
    )

    result = acceptance_executor.enqueue_manifest_paper(paper)

    assert getattr(captured["payload"], "urls") == ["https://example.com/paper"]
    assert getattr(captured["payload"], "force_refresh") is True
    assert result == {"request_id": "req-web-1", "paper_task_id": "web-paper-1"}


def test_enqueue_api_manifest_paper_reuses_pubmed_submit_for_pubmed_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paper = AcceptancePaperRecord.model_validate(
        {
            "paper_id": "api-pubmed-001",
            "entry_kind": "api",
            "source": "pubmed",
            "request_payload": {
                "task_form": "{\"goal\":\"LDLR\",\"disease\":\"FH\",\"country\":\"CN\",\"language\":\"EN\"}",
                "query": "LDLR",
                "identifiers": ["PMID:99999999"],
            },
            "status": "queued",
        }
    )
    captured: dict[str, object] = {}

    def fake_submit_pubmed_selection(payload: object) -> TaskRequestCreateResponse:
        captured["payload"] = payload
        return TaskRequestCreateResponse(
            request_id="req-pubmed-1",
            status="queued",
            papers=[
                PaperTaskItemResponse(
                    paper_task_id="pubmed-paper-1",
                    filename="PMID:99999999",
                    status="queued",
                )
            ],
        )

    monkeypatch.setattr(
        acceptance_executor,
        "submit_pubmed_selection",
        fake_submit_pubmed_selection,
    )

    result = acceptance_executor.enqueue_manifest_paper(paper)

    assert getattr(captured["payload"], "selected_pmids") == ["99999999"]
    assert getattr(captured["payload"], "target") == "LDLR"
    assert result == {"request_id": "req-pubmed-1", "paper_task_id": "pubmed-paper-1"}


def test_enqueue_api_manifest_paper_routes_non_pubmed_to_internal_submit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paper = AcceptancePaperRecord.model_validate(
        {
            "paper_id": "api-001",
            "entry_kind": "api",
            "source": "pmc",
            "request_payload": {
                "task_form": "{\"goal\":\"BARD1\",\"disease\":\"Breast cancer\",\"country\":\"US\",\"language\":\"EN\"}",
                "query": "BARD1 hereditary breast cancer",
                "identifiers": ["PMCID:PMC1234567"],
            },
            "status": "queued",
        }
    )
    captured: dict[str, object] = {}

    def fake_submit_api_acceptance_item(**kwargs: object) -> dict[str, str]:
        captured.update(kwargs)
        return {"request_id": "req-api-1", "paper_task_id": "api-paper-1"}

    monkeypatch.setattr(
        acceptance_executor,
        "submit_api_acceptance_item",
        fake_submit_api_acceptance_item,
    )

    result = acceptance_executor.enqueue_manifest_paper(paper)

    assert captured["source"] == "pmc"
    assert captured["request_payload"] == {
        "task_form": "{\"goal\":\"BARD1\",\"disease\":\"Breast cancer\",\"country\":\"US\",\"language\":\"EN\"}",
        "query": "BARD1 hereditary breast cancer",
        "identifiers": ["PMCID:PMC1234567"],
    }
    assert result == {"request_id": "req-api-1", "paper_task_id": "api-paper-1"}
