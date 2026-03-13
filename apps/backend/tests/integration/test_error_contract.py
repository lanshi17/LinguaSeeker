from __future__ import annotations

import hashlib
from types import SimpleNamespace
from typing import Any, Dict, Generator

import pytest
from fastapi.testclient import TestClient

import main
import src.api.routes.core as api_module
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


def test_upload_wrong_content_type_returns_contract(client: TestClient) -> None:
    response = client.post(f"{cfg.api_prefix}/pdf/upload", json={"foo": "bar"})
    assert response.status_code == 415
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["error_code"] == "FILE_TYPE_UNSUPPORTED"
    assert "log_link" in payload


def test_task_create_validation_returns_contract(client: TestClient) -> None:
    response = client.post(f"{cfg.api_prefix}/tasks", json={})
    assert response.status_code == 422
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["error_code"] == "INPUT_INVALID"
    assert "log_link" in payload
    assert "errors" in payload


def test_log_reissue_success(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeRedisConn:
        def __init__(self) -> None:
            self.counter = 0

        def incr(self, key: str) -> int:
            assert key == "log_reissue:req-12345"
            self.counter += 1
            return self.counter

        def expire(self, key: str, ttl: int) -> bool:
            assert key == "log_reissue:req-12345"
            assert ttl == 60
            return True

    class FakeRedisClient:
        def __init__(self) -> None:
            self.conn = FakeRedisConn()

        def get_connection(self) -> FakeRedisConn:
            return self.conn

    monkeypatch.setattr(api_module, "redis_client", FakeRedisClient())
    response = client.get(f"{cfg.api_prefix}/logs/reissue?request_id=req-12345")
    assert response.status_code == 200
    payload = response.json()
    assert payload["request_id"] == "req-12345"
    assert payload["log_link"].endswith("/logs/reissue?request_id=req-12345")


def test_log_reissue_rate_limit(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeRedisConn:
        def incr(self, _: str) -> int:
            return 2

        def expire(self, _: str, __: int) -> bool:
            return True

    class FakeRedisClient:
        def get_connection(self) -> FakeRedisConn:
            return FakeRedisConn()

    monkeypatch.setattr(api_module, "redis_client", FakeRedisClient())
    response = client.get(f"{cfg.api_prefix}/logs/reissue?request_id=req-23456")
    assert response.status_code == 429
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["error_code"] == "INPUT_INVALID"


def test_download_processed_result_not_found_returns_resource_not_found(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class DummyMinio:
        async def download_processed_result(self, object_key: str) -> bytes:
            raise FileNotFoundError(object_key)

    monkeypatch.setattr(api_module, "MinIOClient", DummyMinio)
    response = client.get(f"{cfg.api_prefix}/results/doc-1/path/to/file.json")
    assert response.status_code == 404
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["error_code"] == "RESOURCE_NOT_FOUND"


def test_pdf_upload_chinese_filename_keeps_metadata_ascii(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    upload_filename = "贵州省Waardenburg综合征新发变异 1 例及文献回顾_岳慧玲.pdf"
    payload = b"%PDF-1.7 chinese-name"
    file_hash = hashlib.sha256(payload).hexdigest()

    captured_upload: Dict[str, Any] = {}

    class DummyPostgres:
        def find_document_by_hash(self, _: str) -> None:
            return None

        def create_document(self, **kwargs: Any) -> Any:
            return SimpleNamespace(document_id=kwargs["document_id"])

    class DummyAsyncResult:
        id = "celery-task-1"

    class DummyTask:
        def apply_async(self, *args: Any, **kwargs: Any) -> DummyAsyncResult:
            return DummyAsyncResult()

    class DummyMinio:
        @staticmethod
        def build_literature_object_key(file_hash: str, original_filename: str | None) -> str:
            return f"{file_hash}/dummy.pdf"

        async def file_exists(self, bucket: str, object_key: str) -> bool:
            return False

        async def upload_literature_upload(self, **kwargs: Any) -> Any:
            captured_upload.update(kwargs)
            return SimpleNamespace(object_key=kwargs["storage_key"])

    monkeypatch.setattr(api_module, "get_postgres_client", lambda: DummyPostgres())
    monkeypatch.setattr(api_module, "get_cached_pdf_result", lambda _: None)
    monkeypatch.setattr(api_module, "process_pdf_task", DummyTask())
    monkeypatch.setattr(api_module, "MinIOClient", DummyMinio)

    response = client.post(
        f"{cfg.api_prefix}/pdf/upload",
        files=[("file", (upload_filename, payload, "application/pdf"))],
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "queued"
    assert body["filename"] == upload_filename
    assert body["upload_key"].startswith(f"{file_hash}/")

    metadata = captured_upload["metadata"]
    assert metadata["hash"] == file_hash
    assert "uploaded_at" in metadata
    assert "filename" not in metadata


def test_check_pdf_hash_redis_failure_returns_internal_error(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that Redis failures in check_pdf_hash return INTERNAL_ERROR."""

    def failing_get_cached_pdf_result(_hash: str) -> None:
        raise ConnectionError("Redis unavailable")

    monkeypatch.setattr(api_module, "get_cached_pdf_result", failing_get_cached_pdf_result)
    response = client.get(f"{cfg.api_prefix}/pdf/check_hash?hash={'a' * 64}")
    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["error_code"] == "INTERNAL_ERROR"
    assert "log_link" in payload


def test_log_reissue_redis_failure_returns_internal_error(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that Redis failures in reissue_log_link return INTERNAL_ERROR."""

    class FakeRedisClient:
        def get_connection(self) -> None:
            raise ConnectionError("Redis unavailable")

    monkeypatch.setattr(api_module, "redis_client", FakeRedisClient())
    response = client.get(f"{cfg.api_prefix}/logs/reissue?request_id=req-99999")
    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["error_code"] == "INTERNAL_ERROR"
    assert "log_link" in payload
