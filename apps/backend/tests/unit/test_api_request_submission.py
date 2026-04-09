from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from src.services.api_request_submission import submit_api_acceptance_item


def test_submit_api_acceptance_item_creates_request_document_and_paper_task() -> None:
    request_id = uuid4()
    document_id = uuid4()
    paper_task_id = uuid4()
    created: dict[str, object] = {}

    class FakeAsyncResult:
        id = "api-task-1"

    class FakeTask:
        def apply_async(self, args: list[object]) -> FakeAsyncResult:
            created["async_args"] = args
            return FakeAsyncResult()

    class FakePostgres:
        def create_task_request(self, **kwargs: object) -> object:
            created["task_request"] = kwargs
            return SimpleNamespace(request_id=request_id, status="queued")

        def find_latest_paper_task_by_hash(self, _: str) -> object:
            return None

        def find_document_by_hash(self, _: str) -> object:
            return None

        def create_document(self, **kwargs: object) -> object:
            created["document"] = kwargs
            return SimpleNamespace(document_id=document_id)

        def create_paper_task(self, **kwargs: object) -> object:
            created["paper_task"] = kwargs
            return SimpleNamespace(paper_task_id=paper_task_id)

        def append_paper_task_log(self, *args: object, **kwargs: object) -> object:
            created.setdefault("logs", []).append((args, kwargs))
            return None

        def update_paper_task(self, _: object, **kwargs: object) -> object:
            created["updated_paper_task"] = kwargs
            return SimpleNamespace(
                paper_task_id=paper_task_id,
                celery_task_id=kwargs.get("celery_task_id"),
            )

        def refresh_task_request_status(self, _: object) -> object:
            return SimpleNamespace(request_id=request_id, status="queued")

    result = submit_api_acceptance_item(
        source="pmc",
        request_payload={
            "task_form": "{\"goal\":\"BARD1\",\"disease\":\"Breast cancer\",\"country\":\"US\",\"language\":\"EN\"}",
            "query": "BARD1 hereditary breast cancer",
            "identifiers": ["PMCID:PMC1234567"],
            "selected_title": "Functional analysis of BARD1",
            "detail_link": "https://pmc.ncbi.nlm.nih.gov/articles/PMC1234567/",
        },
        postgres=FakePostgres(),
        task_handler=FakeTask(),
    )

    assert result == {
        "request_id": str(request_id),
        "paper_task_id": str(paper_task_id),
    }
    assert created["task_request"] == {
        "task_form_text": "{\"goal\":\"BARD1\",\"disease\":\"Breast cancer\",\"country\":\"US\",\"language\":\"EN\"}",
        "status": "queued",
        "metadata": {
            "entry": "api",
            "source": "pmc",
            "request_payload": {
                "query": "BARD1 hereditary breast cancer",
                "identifiers": ["PMCID:PMC1234567"],
                "selected_title": "Functional analysis of BARD1",
                "detail_link": "https://pmc.ncbi.nlm.nih.gov/articles/PMC1234567/",
            },
        },
    }
    assert created["document"] == {
        "title": "Functional analysis of BARD1",
        "original_filename": "Functional analysis of BARD1",
        "local_path": "https://pmc.ncbi.nlm.nih.gov/articles/PMC1234567/",
        "file_hash": created["paper_task"]["file_hash"],
        "status": "queued",
        "summary": "Queued api acceptance source: pmc",
    }
    assert created["async_args"] == [
        "pmc",
        {
            "query": "BARD1 hereditary breast cancer",
            "identifiers": ["PMCID:PMC1234567"],
            "selected_title": "Functional analysis of BARD1",
            "detail_link": "https://pmc.ncbi.nlm.nih.gov/articles/PMC1234567/",
        },
        str(document_id),
        str(paper_task_id),
        str(request_id),
    ]


def test_submit_api_acceptance_item_enqueues_process_api_paper_task() -> None:
    request_id = uuid4()
    document_id = uuid4()
    paper_task_id = uuid4()
    called: dict[str, object] = {"apply_async": False}

    class FakeAsyncResult:
        id = "api-task-1"

    class FakeTask:
        def apply_async(self, args: list[object]) -> FakeAsyncResult:
            called["apply_async"] = True
            called["args"] = args
            return FakeAsyncResult()

    class FakePostgres:
        def create_task_request(self, **_: object) -> object:
            return SimpleNamespace(request_id=request_id, status="queued")

        def find_latest_paper_task_by_hash(self, _: str) -> object:
            return None

        def find_document_by_hash(self, _: str) -> object:
            return None

        def create_document(self, **_: object) -> object:
            return SimpleNamespace(document_id=document_id)

        def create_paper_task(self, **_: object) -> object:
            return SimpleNamespace(paper_task_id=paper_task_id)

        def append_paper_task_log(self, *_: object, **__: object) -> object:
            return None

        def update_paper_task(self, _: object, **kwargs: object) -> object:
            called["celery_task_id"] = kwargs.get("celery_task_id")
            return SimpleNamespace(paper_task_id=paper_task_id)

        def refresh_task_request_status(self, _: object) -> object:
            return SimpleNamespace(request_id=request_id, status="queued")

    submit_api_acceptance_item(
        source="crossref",
        request_payload={
            "task_form": "{\"goal\":\"BARD1\",\"disease\":\"Breast cancer\",\"country\":\"US\",\"language\":\"EN\"}",
            "query": "BARD1 hereditary breast cancer",
            "identifiers": ["DOI:10.1000/example"],
        },
        postgres=FakePostgres(),
        task_handler=FakeTask(),
    )

    assert called["apply_async"] is True
    assert called["celery_task_id"] == "api-task-1"
