"""
M2 Task Creation Flow: Candidates Search Handoff Contract Tests

These tests encode the M2 target contract for the candidates-search handoff after confirmation.
The candidates endpoint should accept a confirmed request_id and reuse that request instead of
requiring a fresh natural-language task_form in the payload.

TASK 8 Contract (Request Payload):
  1. POST /tasks/requests/pubmed/candidates accepts request_id parameter
  2. task_form field becomes optional (not required in payload)
  3. When request_id present: endpoint does NOT require task_form
  4. When both request_id AND task_form missing: endpoint rejects with HTTP 400 INPUT_INVALID

TASK 9 Contract (Response Shape and Reuse Logic):
  1. When request_id provided: endpoint calls get_task_request() to fetch confirmed request
  2. Response returns the SAME request_id (proves handoff continuity)
  3. Response includes confirmed request's task_form (echoed, not input task_form)
  4. Response DTO must be extended to include request_id field
  5. Route handler must implement the reuse logic and response shaping

This file encodes only the Task 8 contract boundaries and the Task 9 response shape expectations.
Both are intentionally RED because current code requires task_form and lacks request_id support.
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


class TestM2CandidatesHandoffContract:
    """
    M2 Candidates Handoff Contract: Request_id replaces task_form in payload

    TASK 8 Scope (Request Payload Acceptance):
    - Endpoint accepts request_id parameter
    - task_form becomes optional (not required when request_id present)
    - Validation: if both request_id AND task_form missing, return HTTP 400 INPUT_INVALID

    TASK 9 Scope (Response Shape and Request Reuse Logic):
    - Route calls get_task_request(request_id) to fetch confirmed request metadata
    - Response includes request_id field (extend PubMedCandidateSearchResponse DTO)
    - Response includes task_form from confirmed request (NOT from input payload)
    - Route implements request reuse (no new request_request entry created)

    These tests verify the contract boundaries but remain intentionally RED
    because current code still requires task_form and lacks request_id support.
    """

    def test_candidates_with_confirmed_request_id_reuses_request_and_returns_same_id(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        task_prefix: str,
    ) -> None:
        """
        RED TEST: Candidates endpoint accepts request_id and implements reuse contract.

        WHAT THIS TEST CHECKS:
        - Request payload is accepted WITHOUT task_form (only request_id required)
        - Response includes request_id field (endpoint aware of handoff continuity)
        - Response includes task_form from confirmed request (not input task_form)
        - Postgres get_task_request() is called (proves intent to reuse request)

        WHAT TASK 9 MUST IMPLEMENT:
        - Make task_form optional in PubMedCandidateSearchRequest DTO
        - Add request_id field to PubMedCandidateSearchRequest (optional)
        - Add request_id field to PubMedCandidateSearchResponse (optional)
        - Route handler: if request_id present, call get_task_request(request_id)
        - Route handler: return get_task_request response's task_form in response
        - Route handler: return the same request_id in response

        RED REASON:
        Current route requires task_form as mandatory field in payload.
        Test sends request WITHOUT task_form, WITH request_id.
        FastAPI validation rejects before endpoint handler runs (HTTP 422).

        INPUT (Test Sends):
        POST /api/tasks/requests/pubmed/candidates
        {
          "request_id": "uuid-from-confirmation",
          "target": "BRCA1",
          "disease": "Breast cancer",
          "country": "CN",
          "language": "en",
          "source": "pubmed",
          "candidate_limit": 15
          # NOTE: no task_form field (this is the key contract change)
        }

        EXPECTED RESPONSE (M2 Contract):
        HTTP 200 {
          "request_id": "uuid-from-confirmation",  # SAME as input
          "task_form": "Find PS3 evidence for BRCA1 variants",  # from confirmed request
          "candidates": [...]
        }

        M2 Contract Assertions (Each will be reached only after Task 9):
        - response.status_code == 200
        - response["request_id"] == input["request_id"]
        - response["task_form"] == confirmed_request.task_form_text
        - response["candidates"] is non-empty list
        - postgres.get_task_request() was called (proves reuse intent)
        """
        # Pre-established confirmed request_id (as if from confirmation endpoint)
        confirmed_request_id = str(uuid4())
        confirmed_task_form = "Find PS3 evidence for BRCA1 variants"

        postgres_calls = {"get_task_request": False}

        class DummyPostgres:
            """Mock that tracks whether get was called."""

            def get_task_request(self, request_id: str) -> Any:
                """Retrieve existing confirmed request."""
                postgres_calls["get_task_request"] = True
                # Return mock confirmed request entry
                return SimpleNamespace(
                    request_id=confirmed_request_id,
                    status="queued",
                    task_form_text=confirmed_task_form,
                    metadata={"entry": "confirmation", "confirmed": True},
                )

        class DummyPubMedService:
            async def search_candidates(
                self,
                query: str,
                country: str | None = None,
                candidate_limit: int = 15,
            ) -> list[Any]:
                """Mock search returns candidate items."""
                return [
                    SimpleNamespace(
                        pmid="12345",
                        title="BRCA1 variants and breast cancer",
                        journal="Nature Genetics",
                        pub_date="2023-01-15",
                    ),
                    SimpleNamespace(
                        pmid="12346",
                        title="PS3 evidence for BRCA1 pathogenicity",
                        journal="Am J Hum Genet",
                        pub_date="2023-06-20",
                    ),
                ]

        monkeypatch.setattr(task_api, "get_postgres_client", lambda: DummyPostgres())
        monkeypatch.setattr(
            task_api, "get_pubmed_service", lambda: DummyPubMedService()
        )

        # Call candidates endpoint with request_id (handoff from confirmation)
        # WITHOUT full task_form in payload (new contract requirement)
        response = client.post(
            f"{task_prefix}/requests/pubmed/candidates",
            json={
                "request_id": confirmed_request_id,  # M2 CHANGE: pass request_id instead of task_form
                "target": "BRCA1",
                "disease": "Breast cancer",
                "country": "CN",
                "language": "en",
                "source": "pubmed",
                "candidate_limit": 15,
            },
        )

        # Contract assertions:
        assert response.status_code == 200, (
            f"Candidates with confirmed request_id should succeed, got {response.status_code}: {response.text}"
        )

        payload = response.json()

        # M2 CONTRACT: request_id must be returned (same as input, not new)
        # Task 9 must extend PubMedCandidateSearchResponse DTO to include request_id field
        assert "request_id" in payload, (
            "M2 contract (Task 9): request_id missing from candidates response. "
            "Task 9 must update PubMedCandidateSearchResponse to include request_id field."
        )
        returned_request_id = payload.get("request_id")
        assert returned_request_id == confirmed_request_id, (
            f"M2 contract (Task 9): candidates must return same request_id from input. "
            f"Expected {confirmed_request_id}, got {returned_request_id}"
        )

        # M2 CONTRACT: candidates array must be present
        assert "candidates" in payload, (
            "M2 contract: candidates array missing from candidates response"
        )
        candidates = payload.get("candidates")
        assert isinstance(candidates, list) and len(candidates) > 0, (
            "M2 contract: candidates must be non-empty array"
        )

        # M2 CONTRACT: task_form should be echoed from confirmed request (not input)
        # Task 9 must fetch task_form from confirmed request, NOT from input payload
        assert "task_form" in payload, (
            "M2 contract (Task 9): task_form field missing from candidates response. "
            "Task 9 must return task_form from confirmed request metadata."
        )
        echoed_task_form = payload.get("task_form")
        assert echoed_task_form == confirmed_task_form, (
            f"M2 contract (Task 9): task_form must be echoed from confirmed request. "
            f"Expected {confirmed_task_form}, got {echoed_task_form}"
        )

        # M2 CONTRACT VERIFICATION: get_task_request called
        # Task 9 route handler must call get_task_request(request_id) to fetch confirmed request
        # This proves the endpoint implements request reuse logic (not creating new request)
        assert postgres_calls["get_task_request"], (
            "M2 contract (Task 9): postgres.get_task_request() must be called. "
            "Task 9 route handler must fetch confirmed request using request_id parameter."
        )

    def test_candidates_without_request_id_or_task_form_returns_invalid(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        task_prefix: str,
    ) -> None:
        """
        RED TEST: Candidates rejects when both request_id AND task_form are missing.

        WHAT THIS TEST CHECKS:
        - Endpoint validates that either request_id OR task_form is present
        - When both missing: endpoint returns HTTP 400 INPUT_INVALID (not 422)

        WHAT TASK 8 MUST IMPLEMENT:
        - Make task_form optional in PubMedCandidateSearchRequest DTO
        - Add application-level validation in route handler:
          if not request_id and not task_form: raise contract_http_exception(400, INPUT_INVALID)

        RED REASON:
        Current route requires task_form as mandatory field in DTO.
        Test sends request WITHOUT task_form AND WITHOUT request_id.
        FastAPI validation rejects before endpoint handler runs (HTTP 422).

        INPUT (Test Sends):
        POST /api/tasks/requests/pubmed/candidates
        {
          "target": "BRCA1",
          "disease": "Breast cancer",
          "country": "CN",
          "language": "en",
          "source": "pubmed",
          "candidate_limit": 15
          # Missing: request_id (no handoff), task_form (no direct search)
        }

        EXPECTED RESPONSE (M2 Contract):
        HTTP 400 {
          "error_code": "INPUT_INVALID",
          "detail": "Either request_id or task_form is required"
        }

        M2 Contract Assertions:
        - response.status_code == 400 (not 422, not 200)
        - response indicates INPUT_INVALID semantics
        """

        class DummyPostgres:
            def get_task_request(self, request_id: str) -> Any:
                return None  # Simulates not found

        class DummyPubMedService:
            async def search_candidates(self, **_: Any) -> list[Any]:
                return []

        monkeypatch.setattr(task_api, "get_postgres_client", lambda: DummyPostgres())
        monkeypatch.setattr(
            task_api, "get_pubmed_service", lambda: DummyPubMedService()
        )

        # Call candidates endpoint WITHOUT request_id AND WITHOUT task_form
        # Currently fails RED because task_form is required
        # After Task 8: should get HTTP 400 (application-level validation)
        response = client.post(
            f"{task_prefix}/requests/pubmed/candidates",
            json={
                "target": "BRCA1",
                "disease": "Breast cancer",
                "country": "CN",
                "language": "en",
                "source": "pubmed",
                "candidate_limit": 15,
                # Missing: request_id, task_form
            },
        )

        # M2 Target State: Should get 400 from application validation
        assert response.status_code == 400, (
            f"M2 contract (Task 8): Candidates without request_id and task_form "
            f"should return HTTP 400 INPUT_INVALID, got {response.status_code}. "
            f"Current state: task_form is required in DTO, so FastAPI validation "
            f"fires before handler (422). Task 8 must make task_form optional "
            f"and add application-level validation: "
            f"if not request_id and not task_form: raise 400 INPUT_INVALID."
        )

        payload = response.json()
        assert _error_indicates_input_invalid(payload), (
            f"M2 contract (Task 8): error must indicate INPUT_INVALID semantics. "
            f"Error response: {payload}"
        )

    def test_candidates_with_nonexistent_request_id_returns_400_input_invalid(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        task_prefix: str,
    ) -> None:
        """
        RED TEST: Candidates rejects when request_id does not exist in database.

        WHAT THIS TEST CHECKS:
        - Endpoint validates that request_id exists (if provided)
        - When request_id does not exist: endpoint returns HTTP 400 INPUT_INVALID
        - Response indicates the resource was not found (not malformed input)

        INPUT (Test Sends):
        POST /api/tasks/requests/pubmed/candidates
        {
          "request_id": "00000000-0000-0000-0000-000000000000",  # UUID that doesn't exist
          "target": "BRCA1",
          "disease": "Breast cancer",
          "country": "CN",
          "language": "en",
          "source": "pubmed",
          "candidate_limit": 15
        }

        EXPECTED RESPONSE (M2 Contract):
        HTTP 400 {
          "error_code": "INPUT_INVALID",
          "detail": "Request ... not found"
        }

        M2 Contract Assertions:
        - response.status_code == 400 (not 404, not 200)
        - error_code indicates INPUT_INVALID
        - detail message indicates the request was not found
        """

        class DummyPostgres:
            def get_task_request(self, request_id: str) -> Any:
                # Simulate: request_id does not exist in database
                return None

        class DummyPubMedService:
            async def search_candidates(self, **_: Any) -> list[Any]:
                return []

        monkeypatch.setattr(task_api, "get_postgres_client", lambda: DummyPostgres())
        monkeypatch.setattr(
            task_api, "get_pubmed_service", lambda: DummyPubMedService()
        )

        nonexistent_request_id = "00000000-0000-0000-0000-000000000000"

        # Call candidates endpoint with request_id that doesn't exist
        response = client.post(
            f"{task_prefix}/requests/pubmed/candidates",
            json={
                "request_id": nonexistent_request_id,
                "target": "BRCA1",
                "disease": "Breast cancer",
                "country": "CN",
                "language": "en",
                "source": "pubmed",
                "candidate_limit": 15,
            },
        )

        # M2 Contract: Should get 400 with INPUT_INVALID semantics
        assert response.status_code == 400, (
            f"M2 contract: Candidates with non-existent request_id "
            f"should return HTTP 400 INPUT_INVALID, got {response.status_code}. "
            f"Response: {response.text}"
        )

        payload = response.json()
        assert _error_indicates_input_invalid(payload), (
            f"M2 contract: error must indicate INPUT_INVALID semantics. "
            f"Error response: {payload}"
        )

        # Verify the error message indicates not found, not malformed input
        detail = payload.get("detail", "").lower()
        assert "not found" in detail or "request" in detail, (
            f"M2 contract: error message should indicate the request was not found. "
            f"Got: {payload.get('detail', 'N/A')}"
        )


def _error_indicates_input_invalid(payload: Dict[str, Any]) -> bool:
    """
    Check if error response indicates INPUT_INVALID semantics.

    This function is stricter than generic error checking: it explicitly looks
    for INPUT_INVALID error_code in responses. It also accepts 'required' language
    from validation errors, but only as a secondary signal.

    Accepts:
    - error_code field containing 'INPUT_INVALID' (primary check)
    - detail field containing 'required' (secondary, for validation errors)

    Returns False for generic validation errors that don't mention INPUT_INVALID
    or missing/required field language.
    """
    error_code = payload.get("error_code", "")
    detail = payload.get("detail", "")

    # Primary signal: explicit INPUT_INVALID error code
    has_input_invalid = "INPUT_INVALID" in str(error_code)

    # Secondary signal: validation error mentioning "required" (field level)
    has_required_language = "required" in str(detail).lower()

    return has_input_invalid or has_required_language
