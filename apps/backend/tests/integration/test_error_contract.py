from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import main
import src.presentation.api as api_module
from src.config import settings as cfg
from src.database.minio_client import MinIOClient


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
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
