"""
M2 Task Creation Flow: Upload Branch Handoff Contract Tests

These tests encode the M2 target contract for the upload-branch handoff after confirmation.
The upload endpoint should reuse an existing confirmed request (by request_id) instead of
requiring a fresh natural-language task_form.

Contract:
1. POST /tasks/requests/upload with confirmed request_id + files (no task_form required)
2. On success: returns the same request_id, papers array, and queued/success status
3. On missing request_id or invalid request: rejects with INPUT_INVALID or appropriate semantics
4. Reuses confirmed request metadata instead of creating a new request entry
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any, Dict
from uuid import uuid4
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import main
from src.infrastructure.minio import MinIOClient
import src.api.routes.task as task_api


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    """Test client with mocked external dependencies."""

    async def _ensure_buckets(self) -> None:
        return None

    monkeypatch.setattr(main, "check_all_connections", lambda: {"redis": True})
    monkeypatch.setattr(MinIOClient, "ensure_buckets", _ensure_buckets, raising=True)

    with TestClient(main.app) as test_client:
        yield test_client


@pytest.fixture()
def task_prefix() -> str:
    # Use app_config (same as main.py) not settings
    from src.config import app_config as cfg

    return f"{cfg.api_prefix}/tasks"


class TestM2UploadBranchHandoffContract:
    """
    M2 Upload Branch Handoff Contract: Accept confirmed request_id + files

    After confirmation flow (clarification + confirmation), the upload branch should:
    1. Accept a confirmed request_id (from POST /interaction/confirm response)
    2. Accept files without requiring a new task_form
    3. Reuse the existing confirmed request instead of creating a new one
    4. Return the same request_id in response (proving handoff continuity)

    This test encodes the minimal gap for Task 7 implementation: the upload route
    must support the request_id-based handoff from the confirmation endpoint.
    """

    def test_upload_with_confirmed_request_id_reuses_request_and_returns_same_id(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        task_prefix: str,
    ) -> None:
        """
        RED TEST: Upload branch accepts confirmed request_id and reuses that request.

        Flow:
        1. User confirms task form via POST /tasks/interaction/confirm
           → Gets request_id (e.g., "uuid-1234")
        2. User submits files via POST /tasks/requests/upload with request_id + files
           → Upload branch should reuse request_id from confirmation
           → Should NOT create new request_id
           → Should return same request_id in response

        Input:
        - request_id: confirmed request UUID from confirmation endpoint
        - files: one or more PDF/DOCX files
        - NO task_form field (should not be required)

        Expected behavior:
        - HTTP 200
        - Response includes request_id (SAME as input, not new)
        - Response includes papers array with status/paper_task_ids
        - Database shows request entry reused (existing request_id used)
        - NO new request_request entry created in PostgreSQL

        M2 Contract Assertions:
        - Response must contain request_id (same as input)
        - Response must contain papers (array of paper results)
        - Response status should reflect overall success (queued or success)
        - Postgres.create_task_request() should NOT be called
        - Postgres.get_task_request() should be called (to reuse existing request)
        """
        # Pre-established confirmed request_id (as if from confirmation endpoint)
        confirmed_request_id = str(uuid4())
        paper_task_id = uuid4()
        document_id = uuid4()

        postgres_calls = {"create_task_request": False, "get_task_request": False}

        class DummyPostgres:
            """Mock that tracks whether create vs get was called."""

            def __init__(self) -> None:
                self.paper_entries: list[Any] = []

            def get_task_request(self, request_id: str) -> Any:
                """Retrieve existing confirmed request."""
                postgres_calls["get_task_request"] = True
                # Return mock confirmed request entry
                return SimpleNamespace(
                    request_id=confirmed_request_id,
                    status="queued",
                    task_form_text="Find PS3 evidence for BRCA1 variants",
                    metadata={"entry": "confirmation", "confirmed": True},
                )

            def create_task_request(
                self, task_form_text: str, status: str, metadata: Dict[str, Any]
            ) -> Any:
                """Should NOT be called when request_id is provided."""
                postgres_calls["create_task_request"] = True
                # This should fail the contract if called
                raise AssertionError(
                    "M2 contract violation: create_task_request() called when "
                    "request_id provided. Upload should reuse existing request, not create new."
                )

            def find_document_by_hash(self, _: str) -> Any:
                return None

            def find_latest_paper_task_by_hash(self, _: str) -> Any:
                return None

            def create_document(self, **_: Any) -> Any:
                return SimpleNamespace(document_id=document_id)

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
                return SimpleNamespace(request_id=confirmed_request_id, status="queued")

            def update_paper_task(self, _: Any, **kwargs: Any) -> Any:
                return SimpleNamespace(
                    paper_task_id=paper_task_id,
                    original_filename="upload.pdf",
                    status="queued",
                    error_code=None,
                    duplicate_of=None,
                    document_id=document_id,
                    celery_task_id=kwargs.get("celery_task_id"),
                )

        class DummyAsyncResult:
            id = "celery-paper-1"

        class DummyProcessTask:
            def apply_async(
                self, args: Any, kwargs: Dict[str, Any]
            ) -> DummyAsyncResult:
                # Validate that paper_task_id and request_id are passed
                assert kwargs.get("request_id") == confirmed_request_id, (
                    f"Task should receive request_id={confirmed_request_id}"
                )
                return DummyAsyncResult()

        class DummyMinio:
            @staticmethod
            def build_literature_object_key(
                file_hash: str, original_filename: str | None
            ) -> str:
                return f"{file_hash}/upload.pdf"

            async def upload_literature_upload(self, **_: Any) -> Any:
                return SimpleNamespace(object_key="m2-upload-key")

        monkeypatch.setattr(task_api, "get_postgres_client", lambda: DummyPostgres())
        monkeypatch.setattr(
            task_api, "process_pdf_task", DummyProcessTask(), raising=False
        )
        monkeypatch.setattr(task_api, "MinIOClient", DummyMinio)

        # Call upload endpoint with request_id (handoff from confirmation)
        # WITHOUT task_form (new contract requirement)
        response = client.post(
            f"{task_prefix}/requests/upload",
            data={"request_id": confirmed_request_id},  # M2 CHANGE: pass request_id
            files=[("files", ("m2-test.pdf", b"%PDF-1.7 m2test", "application/pdf"))],
        )

        # Contract assertions:
        assert response.status_code == 200, (
            f"Upload with confirmed request_id should succeed, got {response.status_code}: {response.text}"
        )

        payload = response.json()

        # M2 CONTRACT: request_id must be returned (same as input, not new)
        assert "request_id" in payload, (
            "M2 contract: request_id missing from upload response"
        )
        returned_request_id = payload.get("request_id")
        assert returned_request_id == confirmed_request_id, (
            f"M2 contract: upload must reuse request_id from confirmation. "
            f"Expected {confirmed_request_id}, got {returned_request_id}"
        )

        # M2 CONTRACT: papers array must be present
        assert "papers" in payload, (
            "M2 contract: papers array missing from upload response"
        )
        papers = payload.get("papers")
        assert isinstance(papers, list) and len(papers) > 0, (
            "M2 contract: papers must be non-empty array"
        )

        # M2 CONTRACT: response status should reflect overall state
        assert "status" in payload, (
            "M2 contract: status field missing from upload response"
        )
        status = payload.get("status")
        assert status in ("queued", "success", "partial_failed"), (
            f"M2 contract: status must be one of (queued, success, partial_failed), got {status}"
        )

        # M2 CONTRACT VERIFICATION: get_task_request called, create_task_request NOT called
        # This proves the upload branch reused the confirmed request instead of creating new
        assert postgres_calls["get_task_request"], (
            "M2 contract: postgres.get_task_request() must be called to fetch confirmed request"
        )
        assert not postgres_calls["create_task_request"], (
            "M2 contract violation: postgres.create_task_request() called when "
            "request_id provided. Upload must reuse existing request from confirmation."
        )

    def test_upload_without_request_id_requires_task_form_or_returns_invalid(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        task_prefix: str,
    ) -> None:
        """
        RED TEST: Upload without request_id or task_form should reject with INPUT_INVALID.

        Current RED State:
        - Sends: FILES only (no request_id, no task_form)
        - Currently gets: HTTP 422 (FastAPI form validation fires before handler)
        - Reason: FastAPI validation layer rejects missing required form field (task_form)
          before application code runs

        M2 Target State (Task 7 implementation):
        - When both request_id AND task_form are missing: HTTP 400 INPUT_INVALID
        - Requires: Application-level validation in endpoint handler (not just FastAPI form)
        - Logic: Make task_form optional in signature, then validate in handler code:
          if not request_id and not task_form: raise contract_http_exception(400, INPUT_INVALID)

        This test will remain RED until Task 7 implementation:
        1. Makes task_form optional in function signature
        2. Adds application-level validation for both-missing case

        Input: Files only, no request_id, no task_form
        Expected (M2): HTTP 400 with INPUT_INVALID error

        M2 Contract Assertion:
        - Response must have status_code=400
        - Response must indicate that either request_id OR task_form is required
        - Error semantics must reflect INPUT_INVALID
        """

        class DummyPostgres:
            def create_task_request(self, *_: Any, **__: Any) -> Any:
                return SimpleNamespace(request_id=str(uuid4()), status="queued")

        class DummyMinio:
            @staticmethod
            def build_literature_object_key(
                file_hash: str, original_filename: str | None
            ) -> str:
                return f"{file_hash}/upload.pdf"

            async def upload_literature_upload(self, **_: Any) -> Any:
                return SimpleNamespace(object_key="unused")

        monkeypatch.setattr(task_api, "get_postgres_client", lambda: DummyPostgres())
        monkeypatch.setattr(task_api, "MinIOClient", DummyMinio)

        # Call upload endpoint WITHOUT request_id AND WITHOUT task_form
        # Currently fails RED with HTTP 422 (FastAPI validation layer)
        # After Task 7: should get HTTP 400 (application-level validation)
        response = client.post(
            f"{task_prefix}/requests/upload",
            files=[("files", ("test.pdf", b"%PDF-1.7 test", "application/pdf"))],
        )

        # Current RED State: Gets 422 from FastAPI form validation
        # M2 Target State: Should get 400 from application validation
        assert response.status_code == 400, (
            f"Upload without request_id and task_form should return 400 (INPUT_INVALID), "
            f"got {response.status_code}. "
            f"Note: Currently fails RED at FastAPI validation layer (422) because "
            f"task_form is still required in signature. After Task 7 implementation, "
            f"task_form will be optional and application handler will return 400."
        )

        payload = response.json()
        assert _error_response_indicates_invalid_input(payload), (
            f"M2 contract: error must indicate INPUT_INVALID when both "
            f"request_id and task_form missing. Got: {payload}"
        )


def _error_response_indicates_invalid_input(payload: Dict[str, Any]) -> bool:
    """
    Check if error response indicates INPUT_INVALID semantics.

    Accepts either:
    - error_code field containing 'INPUT_INVALID'
    - detail field containing 'required' or 'invalid' (case-insensitive)
    """
    error_code = payload.get("error_code", "")
    detail = payload.get("detail", "")

    return (
        "INPUT_INVALID" in str(error_code)
        or "required" in str(detail).lower()
        or "invalid" in str(detail).lower()
    )
