from __future__ import annotations

from typing import Generator

import pytest
from fastapi.testclient import TestClient

import main
import src.api.routes.task as task_module
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


def test_start_interaction_missing_input_returns_input_invalid(
    client: TestClient,
) -> None:
    """Test that missing user_input returns INPUT_INVALID error."""
    response = client.post(
        f"{cfg.api_prefix}/tasks/interaction/start",
        json={"user_input": ""},
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["error_code"] == "INPUT_INVALID"
    assert "log_link" in payload


def test_respond_interaction_missing_response_returns_input_invalid(
    client: TestClient,
) -> None:
    """Test that missing user_response returns INPUT_INVALID error."""
    response = client.post(
        f"{cfg.api_prefix}/tasks/interaction/respond",
        json={"session_id": "test-session", "user_response": ""},
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["error_code"] == "INPUT_INVALID"
    assert "log_link" in payload


def test_search_pubmed_candidates_invalid_source_returns_input_invalid(
    client: TestClient,
) -> None:
    """Test that invalid source returns INPUT_INVALID error."""
    response = client.post(
        f"{cfg.api_prefix}/tasks/requests/pubmed/candidates",
        json={
            "source": "invalid",
            "target": "BRCA1",
            "disease": "cancer",
        },
    )
    assert response.status_code == 422  # Pydantic validation error
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["error_code"] == "INPUT_INVALID"
    assert "log_link" in payload


def test_submit_pubmed_selection_empty_pmids_returns_input_invalid(
    client: TestClient,
) -> None:
    """Test that empty selected_pmids returns INPUT_INVALID error."""
    response = client.post(
        f"{cfg.api_prefix}/tasks/requests/pubmed/submit",
        json={
            "source": "pubmed",
            "selected_pmids": [],
            "task_form": "test form",
        },
    )
    assert response.status_code == 422  # Pydantic validation error
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["error_code"] == "INPUT_INVALID"
    assert "log_link" in payload


def test_create_task_request_by_web_crawl_invalid_source_returns_input_invalid(
    client: TestClient,
) -> None:
    """Test that invalid source for web crawl returns INPUT_INVALID error."""
    response = client.post(
        f"{cfg.api_prefix}/tasks/requests/web/crawl",
        json={
            "source": "invalid",
            "urls": ["https://example.com"],
            "task_form": "test form",
        },
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["error_code"] == "INPUT_INVALID"
    assert "log_link" in payload


def test_create_task_request_by_upload_missing_form_returns_input_invalid(
    client: TestClient,
) -> None:
    """Test that missing task_form returns INPUT_INVALID error."""
    response = client.post(
        f"{cfg.api_prefix}/tasks/requests/upload",
        data={"task_form": ""},
        files=[("files", ("test.pdf", b"fake pdf", "application/pdf"))],
    )
    assert response.status_code == 422  # Pydantic validation error
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["error_code"] == "INPUT_INVALID"
    assert "log_link" in payload


def test_resume_paper_task_not_found_returns_resource_not_found(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that missing paper task returns RESOURCE_NOT_FOUND error."""

    class DummyPostgres:
        def get_paper_task(self, paper_task_id: str) -> None:
            return None

    monkeypatch.setattr(task_module, "get_postgres_client", lambda: DummyPostgres())

    response = client.post(
        f"{cfg.api_prefix}/tasks/papers/00000000-0000-0000-0000-000000000001/resume"
    )
    assert response.status_code == 404
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["error_code"] == "RESOURCE_NOT_FOUND"
    assert "log_link" in payload
