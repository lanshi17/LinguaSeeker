from __future__ import annotations

from typing import Any, Dict, List, Tuple
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import main
from src.config import settings as cfg
from src.database.minio_client import MinIOClient
import src.presentation.task_api as task_api


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    async def _ensure_buckets(self) -> None:
        return None

    monkeypatch.setattr(main, "check_all_connections", lambda: {"redis": True})
    monkeypatch.setattr(MinIOClient, "ensure_buckets", _ensure_buckets, raising=True)

    with TestClient(main.app) as test_client:
        yield test_client


@pytest.fixture()
def task_prefix() -> str:
    return f"{cfg.api_prefix}/tasks"


def test_create_task_success(client: TestClient, monkeypatch: pytest.MonkeyPatch, task_prefix: str) -> None:
    class DummyAsyncResult:
        def __init__(self) -> None:
            self.id = "task-123"
            self.status = "PENDING"

    class DummyTask:
        def delay(self, file_paths: List[str], output_root: str | None = None) -> DummyAsyncResult:
            assert file_paths == ["/tmp/sample.pdf"]
            assert output_root is None
            return DummyAsyncResult()

    monkeypatch.setattr(task_api, "process_pdf_task", DummyTask())

    response = client.post(f"{task_prefix}", json={"file_paths": ["/tmp/sample.pdf"]})
    assert response.status_code == 200
    payload = response.json()
    assert payload["task_id"] == "task-123"
    assert payload["status"] == "PENDING"


def test_get_task_status_success(client: TestClient, monkeypatch: pytest.MonkeyPatch, task_prefix: str) -> None:
    class DummyAsyncResult:
        def __init__(self, task_id: str) -> None:
            self.id = task_id
            self.status = "SUCCESS"
            self.result = {"ok": True, "document_id": "doc-999"}

        def failed(self) -> bool:
            return False

        def successful(self) -> bool:
            return True

    monkeypatch.setattr(task_api, "AsyncResult", lambda task_id, app=None: DummyAsyncResult(task_id))

    response = client.get(f"{task_prefix}/task-200")
    assert response.status_code == 200
    payload = response.json()
    assert payload["task_id"] == "task-200"
    assert payload["status"] == "SUCCESS"
    assert payload["document_id"] == "doc-999"
    assert "result" not in payload


def test_get_task_status_failure(client: TestClient, monkeypatch: pytest.MonkeyPatch, task_prefix: str) -> None:
    class DummyAsyncResult:
        def __init__(self, task_id: str) -> None:
            self.id = task_id
            self.status = "FAILURE"
            self.result = "boom"

        def failed(self) -> bool:
            return True

        def successful(self) -> bool:
            return False

    monkeypatch.setattr(task_api, "AsyncResult", lambda task_id, app=None: DummyAsyncResult(task_id))

    response = client.get(f"{task_prefix}/task-500")
    assert response.status_code == 200
    payload = response.json()
    assert payload["task_id"] == "task-500"
    assert payload["status"] == "FAILURE"
    assert payload["error"] == "boom"


def test_list_tasks_with_results(client: TestClient, monkeypatch: pytest.MonkeyPatch, task_prefix: str) -> None:
    metas: List[Dict[str, Any]] = [
        {
            "task_id": "task-1",
            "status": "SUCCESS",
            "date_done": "2026-02-10T10:00:00Z",
            "result": {"done": True},
        },
        {
            "task_id": "task-2",
            "status": "FAILURE",
            "date_done": "2026-02-10T09:00:00Z",
            "result": "bad",
        },
    ]

    def fake_list_celery_task_meta(cursor: int, count: int) -> Tuple[int, List[Dict[str, Any]]]:
        assert cursor == 0
        assert count == 2
        return 0, metas

    monkeypatch.setattr(task_api, "list_celery_task_meta", fake_list_celery_task_meta)

    response = client.get(f"{task_prefix}?limit=2&include_result=true")
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 2
    assert payload["items"][0]["task_id"] == "task-1"
    assert payload["items"][0]["result"] == {"done": True}
    assert payload["items"][1]["task_id"] == "task-2"
    assert payload["items"][1]["error"] == "bad"


def test_create_task_request_upload_duplicate_success(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    task_prefix: str,
) -> None:
    request_id = uuid4()
    paper_task_id = uuid4()
    historical_id = uuid4()
    document_id = uuid4()

    class DummyPostgres:
        def __init__(self) -> None:
            self.paper_entries: List[Any] = []

        def create_task_request(self, task_form_text: str, status: str, metadata: Dict[str, Any]) -> Any:
            assert task_form_text == "Find BRCA1 PS3 evidence"
            return SimpleNamespace(request_id=request_id, status=status)

        def find_document_by_hash(self, _: str) -> Any:
            return SimpleNamespace(document_id=document_id)

        def find_latest_paper_task_by_hash(self, _: str) -> Any:
            return SimpleNamespace(paper_task_id=historical_id)

        def create_paper_task(self, **kwargs: Any) -> Any:
            entry = SimpleNamespace(
                paper_task_id=paper_task_id,
                original_filename=kwargs.get("original_filename"),
                status=kwargs.get("status"),
                error_code=kwargs.get("error_code"),
                duplicate_of=kwargs.get("duplicate_of"),
                document_id=kwargs.get("document_id"),
                celery_task_id=None,
            )
            self.paper_entries.append(entry)
            return entry

        def append_paper_task_log(self, *_: Any, **__: Any) -> Any:
            return None

        def refresh_task_request_status(self, _: Any) -> Any:
            return SimpleNamespace(request_id=request_id, status="success")

    class DummyMinio:
        async def upload_literature_upload(self, **_: Any) -> Any:
            return SimpleNamespace(object_key="unused")

    monkeypatch.setattr(task_api, "get_postgres_client", lambda: DummyPostgres())
    monkeypatch.setattr(task_api, "MinIOClient", lambda: DummyMinio())

    response = client.post(
        f"{task_prefix}/requests/upload",
        data={"task_form": "Find BRCA1 PS3 evidence"},
        files=[("files", ("dup.pdf", b"%PDF-1.7 duplicate", "application/pdf"))],
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["request_id"] == str(request_id)
    assert payload["papers"][0]["status"] == "success"
    assert payload["papers"][0]["error_code"] == "FILE_DUPLICATE"
    assert payload["papers"][0]["duplicate_of"] == str(historical_id)


def test_create_task_request_upload_enqueue_non_duplicate(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    task_prefix: str,
) -> None:
    request_id = uuid4()
    paper_task_id = uuid4()
    document_id = uuid4()

    class DummyAsyncResult:
        id = "celery-paper-1"

    class DummyProcessTask:
        def apply_async(self, args: Any, kwargs: Dict[str, Any]) -> DummyAsyncResult:
            assert len(args[0]) == 1
            assert kwargs["paper_task_id"] == str(paper_task_id)
            assert kwargs["request_id"] == str(request_id)
            return DummyAsyncResult()

    class DummyPostgres:
        def create_task_request(self, *_: Any, **__: Any) -> Any:
            return SimpleNamespace(request_id=request_id, status="queued")

        def find_document_by_hash(self, _: str) -> Any:
            return None

        def find_latest_paper_task_by_hash(self, _: str) -> Any:
            return None

        def create_document(self, **_: Any) -> Any:
            return SimpleNamespace(document_id=document_id)

        def create_paper_task(self, **kwargs: Any) -> Any:
            return SimpleNamespace(
                paper_task_id=paper_task_id,
                original_filename=kwargs.get("original_filename"),
                status=kwargs.get("status"),
                error_code=kwargs.get("error_code"),
                duplicate_of=kwargs.get("duplicate_of"),
                document_id=kwargs.get("document_id"),
                celery_task_id=None,
            )

        def update_paper_task(self, _: Any, **kwargs: Any) -> Any:
            return SimpleNamespace(
                paper_task_id=paper_task_id,
                original_filename="new.pdf",
                status="queued",
                error_code=None,
                duplicate_of=None,
                document_id=document_id,
                celery_task_id=kwargs.get("celery_task_id"),
            )

        def append_paper_task_log(self, *_: Any, **__: Any) -> Any:
            return None

        def refresh_task_request_status(self, _: Any) -> Any:
            return SimpleNamespace(request_id=request_id, status="queued")

    class DummyMinio:
        async def upload_literature_upload(self, **_: Any) -> Any:
            return SimpleNamespace(object_key="hash/new.pdf")

    monkeypatch.setattr(task_api, "get_postgres_client", lambda: DummyPostgres())
    monkeypatch.setattr(task_api, "MinIOClient", lambda: DummyMinio())
    monkeypatch.setattr(task_api, "process_pdf_task", DummyProcessTask())

    response = client.post(
        f"{task_prefix}/requests/upload",
        data={"task_form": "Evaluate LDLR CNV"},
        files=[("files", ("new.pdf", b"%PDF-1.7 new", "application/pdf"))],
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["papers"][0]["status"] == "queued"
    assert payload["papers"][0]["celery_task_id"] == "celery-paper-1"


def test_get_task_request_status(client: TestClient, monkeypatch: pytest.MonkeyPatch, task_prefix: str) -> None:
    request_id = uuid4()
    paper_task_id = uuid4()

    class DummyPostgres:
        def refresh_task_request_status(self, _: Any) -> Any:
            return SimpleNamespace(request_id=request_id, status="running")

        def list_paper_tasks_by_request(self, _: Any) -> List[Any]:
            return [
                SimpleNamespace(
                    paper_task_id=paper_task_id,
                    original_filename="sample.pdf",
                    status="running",
                    error_code=None,
                    duplicate_of=None,
                    document_id=None,
                    celery_task_id="celery-1",
                )
            ]

    monkeypatch.setattr(task_api, "get_postgres_client", lambda: DummyPostgres())
    response = client.get(f"{task_prefix}/requests/{request_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["request_id"] == str(request_id)
    assert payload["status"] == "running"
    assert payload["papers"][0]["paper_task_id"] == str(paper_task_id)


def test_search_pubmed_candidates_success(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    task_prefix: str,
) -> None:
    class DummyPubMedService:
        async def search_candidates(self, query: str, country: str, candidate_limit: int) -> List[Any]:
            assert "BRCA1" in query
            assert country == "不限"
            assert candidate_limit == 5
            return [
                SimpleNamespace(
                    pmid="12345678",
                    title="BRCA1 functional assay evidence",
                    journal="Nature Genetics",
                    pub_date="2025 Jan",
                )
            ]

    monkeypatch.setattr(task_api, "get_pubmed_service", lambda: DummyPubMedService())
    response = client.post(
        f"{task_prefix}/requests/pubmed/candidates",
        json={
            "task_form": "Find BRCA1 PS3 evidence",
            "target": "BRCA1",
            "disease": "Breast cancer",
            "country": "不限",
            "source": "pubmed",
            "candidate_limit": 5,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["task_form"] == "Find BRCA1 PS3 evidence"
    assert payload["candidates"][0]["pmid"] == "12345678"


def test_search_pubmed_candidates_no_result_maps_error_contract(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    task_prefix: str,
) -> None:
    class DummyPubMedService:
        async def search_candidates(self, **_: Any) -> List[Any]:
            return []

    monkeypatch.setattr(task_api, "get_pubmed_service", lambda: DummyPubMedService())
    response = client.post(
        f"{task_prefix}/requests/pubmed/candidates",
        json={
            "task_form": "Find LDLR evidence",
            "target": "LDLR",
            "disease": "Familial Hypercholesterolemia",
            "country": "CN",
            "source": "pubmed",
            "candidate_limit": 5,
        },
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["error_code"] == "FETCH_NO_RESULT"


def test_submit_pubmed_selection(client: TestClient, monkeypatch: pytest.MonkeyPatch, task_prefix: str) -> None:
    request_id = uuid4()
    paper_task_id = uuid4()
    document_id = uuid4()

    class DummyAsyncResult:
        id = "pubmed-task-1"

    class DummyPubMedTask:
        def apply_async(self, args: List[Any]) -> DummyAsyncResult:
            assert args[0] == "99999999"
            return DummyAsyncResult()

    class DummyPostgres:
        def create_task_request(self, *_: Any, **__: Any) -> Any:
            return SimpleNamespace(request_id=request_id, status="queued")

        def get_document_by_pmid(self, _: str) -> Any:
            return None

        def find_latest_paper_task_by_hash(self, _: str) -> Any:
            return None

        def create_document(self, **kwargs: Any) -> Any:
            assert kwargs["pmid"] == "99999999"
            return SimpleNamespace(document_id=document_id)

        def create_paper_task(self, **kwargs: Any) -> Any:
            return SimpleNamespace(
                paper_task_id=paper_task_id,
                original_filename=kwargs.get("original_filename"),
                status=kwargs.get("status"),
                error_code=kwargs.get("error_code"),
                duplicate_of=kwargs.get("duplicate_of"),
                document_id=kwargs.get("document_id"),
                celery_task_id=None,
            )

        def append_paper_task_log(self, *_: Any, **__: Any) -> Any:
            return None

        def update_paper_task(self, _: Any, **kwargs: Any) -> Any:
            return SimpleNamespace(
                paper_task_id=paper_task_id,
                original_filename="PMID:99999999",
                status="queued",
                error_code=None,
                duplicate_of=None,
                document_id=document_id,
                celery_task_id=kwargs.get("celery_task_id"),
            )

        def refresh_task_request_status(self, _: Any) -> Any:
            return SimpleNamespace(request_id=request_id, status="queued")

    monkeypatch.setattr(task_api, "get_postgres_client", lambda: DummyPostgres())
    monkeypatch.setattr(task_api, "process_pubmed_paper_task", DummyPubMedTask())

    response = client.post(
        f"{task_prefix}/requests/pubmed/submit",
        json={
            "task_form": "Evaluate LDLR evidence",
            "selected_pmids": ["99999999"],
            "target": "LDLR",
            "disease": "FH",
            "country": "CN",
            "source": "pubmed",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["request_id"] == str(request_id)
    assert payload["papers"][0]["paper_task_id"] == str(paper_task_id)
    assert payload["papers"][0]["celery_task_id"] == "pubmed-task-1"
