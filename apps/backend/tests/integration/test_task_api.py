from __future__ import annotations

from typing import Any, Dict, List, Tuple

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
            self.result = {"ok": True}

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
    assert payload["result"] == {"ok": True}


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
