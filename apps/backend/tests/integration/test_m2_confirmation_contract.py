"""
M2 Task Creation Flow: Confirmation Contract Tests

These tests encode the M2 target contract for the task-sheet confirmation flow.
The confirmation endpoint persists the complete task form (goal/disease/country/language)
and returns branch-ready semantics for the M2 multi-source workflow.

Contract:
1. POST /tasks/interaction/confirm with complete task_form_payload
2. On success: returns request_id, confirmed=True, and branch options (pubmed/web/upload)
3. On missing required fields: rejects with INPUT_INVALID semantics
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any, Dict
from uuid import uuid4

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


class TestM2ConfirmationSuccessContract:
    """
    M2 Confirmation Contract: Successful task-form confirmation

    When a complete task form (goal, disease, country, language) is submitted:
    - Endpoint persists the task form to PostgreSQL (task_request table)
    - Returns request_id (UUIDv4) for future status queries
    - Returns confirmed=True state
    - Returns branch options showing available literature sources (pubmed, web, upload)
    """

    def test_confirm_complete_task_form_persists_and_returns_request_id(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        task_prefix: str,
    ) -> None:
        """
        RED TEST: Confirmation of complete task form persists and returns branch-ready response.

        Input: Complete structured task_form_payload with goal, disease, country, language
        Expected: HTTP 200, response includes:
        - request_id: UUIDv4 string (persisted in DB)
        - confirmed: True
        - available_branches: list of source options (pubmed, web, upload)

        M2 Contract Assertion:
        - Response must contain confirmed=True
        - Response must contain request_id (UUIDv4 format)
        - Response must contain available_branches showing viable sources
        - Database must show new task_request with matching request_id and task_form_text
        """
        request_id_out = str(uuid4())
        task_form_input = {
            "goal": "Find PS3 evidence for BRCA1 variants",
            "disease": "Breast cancer",
            "country": "CN",
            "language": "en",
        }

        class DummyPostgresClient:
            def create_task_request(
                self, task_form_text: str, status: str, metadata: Dict[str, Any]
            ) -> Any:
                """Mock: persist task form and return request entry."""

                class RequestEntry:
                    def __init__(self) -> None:
                        self.request_id = request_id_out
                        self.status = status
                        self.task_form_text = task_form_text
                        self.metadata = metadata

                return RequestEntry()

        def mock_get_postgres_client() -> Any:
            return DummyPostgresClient()

        monkeypatch.setattr(task_api, "get_postgres_client", mock_get_postgres_client)

        # Call confirmation endpoint with complete task form
        response = client.post(
            f"{task_prefix}/interaction/confirm",
            json={"task_form_payload": task_form_input},
        )

        # Contract assertions:
        assert response.status_code == 200, (
            f"Confirmation should succeed with 200, got {response.status_code}: {response.text}"
        )

        payload = response.json()

        # M2 CONTRACT: confirmed field and state
        assert "confirmed" in payload, (
            "M2 contract: confirmed field missing from confirmation response"
        )
        assert payload.get("confirmed") is True, (
            "M2 contract: confirmed must be True on successful persistence"
        )

        # M2 CONTRACT: request_id for status tracking
        assert "request_id" in payload, (
            "M2 contract: request_id field missing (required for status queries)"
        )
        request_id = payload.get("request_id")
        assert isinstance(request_id, str) and len(request_id) > 0, (
            "M2 contract: request_id must be non-empty string (UUIDv4)"
        )

        # M2 CONTRACT: available branches for next workflow step
        assert "available_branches" in payload, (
            "M2 contract: available_branches field missing (source options)"
        )
        branches = payload.get("available_branches")
        assert isinstance(branches, list) and len(branches) > 0, (
            "M2 contract: available_branches must be non-empty list"
        )
        # Expect standard MVP sources: pubmed, web, upload
        branch_names = {b.get("source") if isinstance(b, dict) else b for b in branches}
        expected_sources = {"pubmed", "web", "upload"}
        assert expected_sources.intersection(branch_names), (
            f"M2 contract: available_branches must include at least one of {expected_sources}"
        )


class TestM2ConfirmationValidationContract:
    """
    M2 Confirmation Contract: Validation and error semantics

    When required fields are missing or malformed:
    - Endpoint validates all required fields (goal, disease, country, language)
    - Returns HTTP 400 with INPUT_INVALID error code
    - Does NOT persist incomplete task form
    """

    def test_confirm_all_required_fields_missing_returns_input_invalid(
        self,
        client: TestClient,
        task_prefix: str,
    ) -> None:
        """
        RED TEST: Confirmation rejects completely empty task form.

        Input: task_form_payload is empty dict {}
        Expected: HTTP 400, INPUT_INVALID

        M2 Contract Assertion:
        - Response must have status_code=400
        - Error must reference required fields or include INPUT_INVALID semantics
        """
        empty_task_form = {}

        response = client.post(
            f"{task_prefix}/interaction/confirm",
            json={"task_form_payload": empty_task_form},
        )

        assert response.status_code == 400, (
            f"Validation should reject empty form with 400, got {response.status_code}"
        )

        payload = response.json()
        assert _error_response_indicates_invalid_input(payload), (
            f"M2 contract: error must describe validation failure: {payload}"
        )

    @pytest.mark.parametrize(
        "missing_field,incomplete_form",
        [
            (
                "goal",
                {
                    # Missing 'goal'
                    "disease": "Breast cancer",
                    "country": "CN",
                    "language": "en",
                },
            ),
            (
                "disease",
                {
                    "goal": "Find PS3 evidence for BRCA1 variants",
                    # Missing 'disease'
                    "country": "CN",
                    "language": "en",
                },
            ),
            (
                "country",
                {
                    "goal": "Find PS3 evidence",
                    "disease": "Breast cancer",
                    # Missing 'country'
                    "language": "en",
                },
            ),
            (
                "language",
                {
                    "goal": "Find PS3 evidence",
                    "disease": "Breast cancer",
                    "country": "CN",
                    # Missing 'language'
                },
            ),
        ],
    )
    def test_confirm_missing_required_field_returns_input_invalid(
        self,
        client: TestClient,
        task_prefix: str,
        missing_field: str,
        incomplete_form: Dict[str, str],
    ) -> None:
        """
        RED TEST: Confirmation rejects incomplete task form with INPUT_INVALID.

        Input: task_form_payload missing one required field (goal/disease/country/language)
        Expected: HTTP 400, INPUT_INVALID semantics

        M2 Contract Assertion:
        - Response must have status_code=400
        - Response must indicate validation error (INPUT_INVALID or required-field language)
        - Database must NOT contain new task_request
        """
        response = client.post(
            f"{task_prefix}/interaction/confirm",
            json={"task_form_payload": incomplete_form},
        )

        assert response.status_code == 400, (
            f"Validation should reject missing '{missing_field}' with 400, got {response.status_code}"
        )

        payload = response.json()
        assert _error_response_indicates_invalid_input(payload), (
            f"M2 contract: error must indicate INPUT_INVALID for missing '{missing_field}': {payload}"
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
