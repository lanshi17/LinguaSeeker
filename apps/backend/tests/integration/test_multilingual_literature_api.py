from __future__ import annotations

from collections.abc import Generator
from types import SimpleNamespace
from typing import Any
from uuid import uuid4
import os

import pytest
from fastapi.testclient import TestClient


for role in [
    "retrieval",
    "parsing",
    "mt",
    "format",
    "vlm",
    "evidence",
    "classification",
    "arbitration",
]:
    os.environ.setdefault(f"{role.upper()}_API_KEY", f"test-{role}-key")
    os.environ.setdefault(f"{role.upper()}_BASE_URL", f"https://test-{role}.example.com")
    os.environ.setdefault(f"{role.upper()}_MODEL", f"test-{role}-model")

os.environ.setdefault("POSTGRES_PASSWORD", "test-postgres-password")
os.environ.setdefault("NEO4J_PASSWORD", "test-neo4j-password")
os.environ.setdefault("MINIO_ACCESS_KEY", "test-minio-access-key")
os.environ.setdefault("MINIO_SECRET_KEY", "test-minio-secret-key")
for proxy_key in [
    "http_proxy",
    "https_proxy",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "all_proxy",
    "ALL_PROXY",
]:
    os.environ.pop(proxy_key, None)

import main
import src.api.routes.task as task_api
from src.config import settings as cfg
from src.infrastructure.minio import MinIOClient


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    async def _ensure_buckets(self) -> None:
        return None

    monkeypatch.setattr(main, "check_all_connections", lambda: {"redis": True})
    monkeypatch.setattr(MinIOClient, "ensure_buckets", _ensure_buckets, raising=True)

    with TestClient(main.app) as test_client:
        yield test_client


@pytest.fixture()
def task_prefix() -> str:
    return f"{cfg.api_prefix}/tasks"


def test_literature_candidates_endpoint_returns_generic_candidates(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    task_prefix: str,
) -> None:
    class DummyPostgres:
        def get_task_request(self, request_id: str) -> Any:
            assert request_id == "req-123"
            return SimpleNamespace(request_id=request_id, task_form_text="Find Fabry disease case reports")

    monkeypatch.setattr(task_api, "get_postgres_client", lambda: DummyPostgres())
    async def fake_search_multilingual_candidates(**_: Any) -> list[dict[str, Any]]:
        return [
            {
                "candidate_id": "cand-1",
                "provider": "jstage",
                "route": "api",
                "title": "Fabry disease case report",
                "language": "ja",
                "identifiers": {"doi": "10.1234/example"},
            }
        ]

    monkeypatch.setattr(
        task_api,
        "search_multilingual_candidates",
        fake_search_multilingual_candidates,
        raising=False,
    )

    response = client.post(
        f"{task_prefix}/requests/literature/candidates",
        json={
            "request_id": "req-123",
            "target": "GLA c.92C>A",
            "disease": "Fabry disease",
            "language": "ja",
            "source": "literature",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["request_id"] == "req-123"
    assert payload["candidates"][0]["provider"] == "jstage"
    assert payload["candidates"][0]["identifiers"]["doi"] == "10.1234/example"


def test_literature_submit_empty_selection_returns_input_invalid(
    client: TestClient,
    task_prefix: str,
) -> None:
    response = client.post(
        f"{task_prefix}/requests/literature/submit",
        json={
            "request_id": "req-123",
            "task_form": "Find Fabry disease case reports",
            "selected_candidates": [],
            "source": "literature",
        },
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["error_code"] == "INPUT_INVALID"


def test_literature_submit_dispatches_web_candidates_to_web_worker(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    task_prefix: str,
) -> None:
    queued: dict[str, Any] = {}

    class DummyAsyncResult:
        id = "celery-web-123"

    class DummyTask:
        def apply_async(self, args: list[Any]) -> DummyAsyncResult:
            queued["args"] = args
            return DummyAsyncResult()

    class DummyPostgres:
        def create_task_request(self, *, task_form_text: str, status: str, metadata: dict[str, Any]) -> Any:
            return SimpleNamespace(request_id="req-1", status=status)

        def create_document(self, **kwargs: Any) -> Any:
            queued["document"] = kwargs
            return SimpleNamespace(document_id="doc-1")

        def create_paper_task(self, **kwargs: Any) -> Any:
            return SimpleNamespace(
                paper_task_id="paper-1",
                document_id=kwargs["document_id"],
                original_filename=kwargs["original_filename"],
                status=kwargs["status"],
                error_code=None,
                duplicate_of=None,
                celery_task_id=None,
            )

        def append_paper_task_log(self, *args: Any, **kwargs: Any) -> None:
            queued["log"] = {"args": args, "kwargs": kwargs}

        def update_paper_task(self, paper_task_id: str, **kwargs: Any) -> Any:
            return SimpleNamespace(
                paper_task_id=paper_task_id,
                document_id="doc-1",
                original_filename="Web candidate",
                status="queued",
                error_code=None,
                duplicate_of=None,
                celery_task_id=kwargs.get("celery_task_id"),
            )

        def refresh_task_request_status(self, request_id: str) -> Any:
            return SimpleNamespace(request_id=request_id, status="queued")

    monkeypatch.setattr(task_api, "get_postgres_client", lambda: DummyPostgres())
    monkeypatch.setattr(task_api, "process_web_page_task", DummyTask())
    monkeypatch.setattr(task_api, "_celery_task", lambda task: task)

    response = client.post(
        f"{task_prefix}/requests/literature/submit",
        json={
            "task_form": "Find Fabry disease case reports",
            "selected_candidates": [
                {
                    "candidate_id": "cand-web",
                    "provider": "pubscholar",
                    "route": "web",
                    "title": "Web candidate",
                    "url": "https://example.com/case-report",
                    "identifiers": {},
                }
            ],
            "source": "literature",
        },
    )

    assert response.status_code == 200
    assert queued["args"] == [
        "https://example.com/case-report",
        "doc-1",
        "paper-1",
        "req-1",
    ]
    assert response.json()["papers"][0]["celery_task_id"] == "celery-web-123"


def test_literature_submit_dispatches_pmid_candidates_to_pubmed_worker(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    task_prefix: str,
) -> None:
    queued: dict[str, Any] = {}

    class DummyAsyncResult:
        id = "celery-pmid-123"

    class DummyTask:
        def apply_async(self, args: list[Any]) -> DummyAsyncResult:
            queued["args"] = args
            return DummyAsyncResult()

    class DummyPostgres:
        def create_task_request(self, *, task_form_text: str, status: str, metadata: dict[str, Any]) -> Any:
            return SimpleNamespace(request_id="req-2", status=status)

        def create_document(self, **kwargs: Any) -> Any:
            return SimpleNamespace(document_id="doc-2")

        def create_paper_task(self, **kwargs: Any) -> Any:
            return SimpleNamespace(
                paper_task_id="paper-2",
                document_id=kwargs["document_id"],
                original_filename=kwargs["original_filename"],
                status=kwargs["status"],
                error_code=None,
                duplicate_of=None,
                celery_task_id=None,
            )

        def append_paper_task_log(self, *args: Any, **kwargs: Any) -> None:
            return None

        def update_paper_task(self, paper_task_id: str, **kwargs: Any) -> Any:
            return SimpleNamespace(
                paper_task_id=paper_task_id,
                document_id="doc-2",
                original_filename="PMID candidate",
                status="queued",
                error_code=None,
                duplicate_of=None,
                celery_task_id=kwargs.get("celery_task_id"),
            )

        def refresh_task_request_status(self, request_id: str) -> Any:
            return SimpleNamespace(request_id=request_id, status="queued")

    monkeypatch.setattr(task_api, "get_postgres_client", lambda: DummyPostgres())
    monkeypatch.setattr(task_api, "process_pubmed_paper_task", DummyTask())
    monkeypatch.setattr(task_api, "_celery_task", lambda task: task)

    response = client.post(
        f"{task_prefix}/requests/literature/submit",
        json={
            "task_form": "Find Fabry disease case reports",
            "selected_candidates": [
                {
                    "candidate_id": "cand-pmid",
                    "provider": "pmc",
                    "route": "api",
                    "title": "PMID candidate",
                    "identifiers": {"pmid": "12345678"},
                }
            ],
            "source": "literature",
        },
    )

    assert response.status_code == 200
    assert queued["args"] == ["12345678", "doc-2", "paper-2", "req-2"]
    assert response.json()["papers"][0]["celery_task_id"] == "celery-pmid-123"


def test_literature_submit_dispatches_identifier_candidates_to_identifier_worker(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    task_prefix: str,
) -> None:
    queued: dict[str, Any] = {}

    class DummyAsyncResult:
        id = "celery-identifier-123"

    class DummyTask:
        def apply_async(self, args: list[Any]) -> DummyAsyncResult:
            queued["args"] = args
            return DummyAsyncResult()

    class DummyPostgres:
        def create_task_request(self, *, task_form_text: str, status: str, metadata: dict[str, Any]) -> Any:
            return SimpleNamespace(request_id="req-3", status=status)

        def create_document(self, **kwargs: Any) -> Any:
            return SimpleNamespace(document_id="doc-3")

        def create_paper_task(self, **kwargs: Any) -> Any:
            return SimpleNamespace(
                paper_task_id="paper-3",
                document_id=kwargs["document_id"],
                original_filename=kwargs["original_filename"],
                status=kwargs["status"],
                error_code=None,
                duplicate_of=None,
                celery_task_id=None,
            )

        def append_paper_task_log(self, *args: Any, **kwargs: Any) -> None:
            return None

        def update_paper_task(self, paper_task_id: str, **kwargs: Any) -> Any:
            return SimpleNamespace(
                paper_task_id=paper_task_id,
                document_id="doc-3",
                original_filename="Identifier candidate",
                status="queued",
                error_code=None,
                duplicate_of=None,
                celery_task_id=kwargs.get("celery_task_id"),
            )

        def refresh_task_request_status(self, request_id: str) -> Any:
            return SimpleNamespace(request_id=request_id, status="queued")

    monkeypatch.setattr(task_api, "get_postgres_client", lambda: DummyPostgres())
    monkeypatch.setattr(task_api, "process_literature_identifier_task", DummyTask())
    monkeypatch.setattr(task_api, "_celery_task", lambda task: task)

    response = client.post(
        f"{task_prefix}/requests/literature/submit",
        json={
            "task_form": "Find Fabry disease case reports",
            "selected_candidates": [
                {
                    "candidate_id": "cand-id",
                    "provider": "jstage",
                    "route": "api",
                    "title": "Identifier candidate",
                    "identifiers": {"doi": "10.1234/example"},
                }
            ],
            "source": "literature",
        },
    )

    assert response.status_code == 200
    assert queued["args"] == [
        {
            "candidate_id": "cand-id",
            "provider": "jstage",
            "route": "api",
            "title": "Identifier candidate",
            "journal": None,
            "year": None,
            "language": None,
            "doi": None,
            "url": None,
            "identifiers": {"doi": "10.1234/example"},
            "detail_link": None,
        },
        "doc-3",
        "paper-3",
        "req-3",
    ]
    assert response.json()["papers"][0]["celery_task_id"] == "celery-identifier-123"
