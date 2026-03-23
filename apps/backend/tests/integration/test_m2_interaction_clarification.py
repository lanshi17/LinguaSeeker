"""
M2 Task Creation Flow: Clarification Contract Tests

These tests encode the M2 target contract for the interaction clarification flow:
1. First response (round 1): Should express needs_clarification semantics
2. Second response (round 2+): Should express task_form_ready semantics with full payload

The contract requires richer semantics than current ready/question/task_form structure.
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


class TestM2FirstClarificationRound:
    """
    M2 Contract: First clarification round (round=1)

    When user input is ambiguous and needs clarification:
    - Response should signal needs_clarification state
    - Should include clarification question
    - Should NOT include complete task_form
    """

    def test_start_interaction_ambiguous_input_returns_needs_clarification(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        task_prefix: str,
    ) -> None:
        """
        RED TEST: First round clarification returns needs_clarification contract.

        User input: "Find evidence for BRCA1"
        Expected: Agent asks clarification question (e.g., about disease context)

        M2 Contract Assertion:
        - Response must contain needs_clarification=True (not just ready=False)
        - Response must contain clarification_question field
        - Response must NOT contain complete task_form
        - Round must be 1
        """
        session_id = str(uuid4())

        class DummyInteractionAgent:
            async def start_interaction(self, user_input: str) -> Dict[str, Any]:
                """
                Simulate agent behavior: ambiguous input needs clarification.
                Returns current DTO structure (will fail M2 assertion).
                """
                return {
                    "session_id": session_id,
                    "ready": False,
                    "task_form": None,
                    "question": "Which disease or condition are you investigating BRCA1 variants in?",
                    "round": 1,
                }

            async def respond_interaction(
                self, session_id: str, user_response: str
            ) -> Dict[str, Any]:
                raise NotImplementedError()

        monkeypatch.setattr(
            task_api, "get_interaction_agent", lambda: DummyInteractionAgent()
        )

        response = client.post(
            f"{task_prefix}/interaction/start",
            json={"user_input": "Find evidence for BRCA1"},
        )

        assert response.status_code == 200
        payload = response.json()

        # Current state (PASSING but incomplete):
        assert payload["ready"] is False
        assert payload["question"] is not None
        assert payload["round"] == 1

        # M2 CONTRACT (FAILING): needs_clarification semantics
        # After implementation, response should include:
        # - needs_clarification=True (new field)
        # - clarification_question (new field, replaces "question")
        # - Must not include task_form
        assert "needs_clarification" in payload, (
            "M2 contract: needs_clarification field missing from round-1 response"
        )
        assert payload.get("needs_clarification") is True, (
            "M2 contract: needs_clarification must be True in round 1"
        )
        assert "clarification_question" in payload, (
            "M2 contract: clarification_question field missing"
        )
        assert payload.get("task_form") is None, (
            "M2 contract: task_form must be None in clarification"
        )


class TestM2SecondClarificationRound:
    """
    M2 Contract: Second clarification round (round=2) to task-form-ready

    When user provides clarification response and task form becomes complete:
    - Response should signal task_form_ready state
    - Should include complete structured task form with all required fields
    - Should include request payload and task_form payload for downstream use
    """

    def test_respond_interaction_complete_form_returns_task_form_ready(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        task_prefix: str,
    ) -> None:
        """
        RED TEST: Second round response returns task_form_ready contract.

        Flow:
        1. start_interaction("Find evidence for BRCA1") → needs_clarification, round=1
        2. respond_interaction(session_id, "Breast cancer") → task_form_ready, round=2

        Expected: Agent extracts full task form from clarification response

        M2 Contract Assertion:
        - Response must contain task_form_ready=True (not just ready=True)
        - Response must contain structured task_form with goal, disease, country, language
        - Response must contain request payload (task_form text for persistence)
        - Round must be 2
        - Must not include question/clarification_question
        """
        session_id = str(uuid4())
        first_round_question = (
            "Which disease or condition are you investigating BRCA1 variants in?"
        )
        clarification_response = "Breast cancer"

        class DummyInteractionAgent:
            async def start_interaction(self, user_input: str) -> Dict[str, Any]:
                """First round: returns clarification question."""
                return {
                    "session_id": session_id,
                    "ready": False,
                    "task_form": None,
                    "question": first_round_question,
                    "round": 1,
                }

            async def respond_interaction(
                self, session_id_param: str, user_response: str
            ) -> Dict[str, Any]:
                """
                Second round: user provided clarification, form is now complete.
                Returns current DTO structure (will fail M2 assertion).
                """
                if user_response != clarification_response:
                    raise ValueError("Unexpected response")

                return {
                    "ready": True,
                    "task_form": {
                        "goal": "Find PS3 evidence",
                        "disease": "Breast cancer",
                        "country": "CN",
                        "language": "en",
                    },
                    "question": None,
                    "round": 2,
                }

        monkeypatch.setattr(
            task_api, "get_interaction_agent", lambda: DummyInteractionAgent()
        )

        # Simulate second round: respond to clarification
        response = client.post(
            f"{task_prefix}/interaction/respond",
            json={"session_id": session_id, "user_response": clarification_response},
        )

        assert response.status_code == 200
        payload = response.json()

        # Current state (PASSING but incomplete):
        assert payload["ready"] is True
        assert payload["task_form"] is not None
        assert payload["round"] == 2

        # M2 CONTRACT (FAILING): task_form_ready semantics
        # After implementation, response should include:
        # - task_form_ready=True (new field)
        # - structured task_form with all fields
        # - request_payload: original task form text for persistence
        # - task_form_payload: enriched payload for downstream (candidates/submit)
        assert "task_form_ready" in payload, (
            "M2 contract: task_form_ready field missing from ready response"
        )
        assert payload.get("task_form_ready") is True, (
            "M2 contract: task_form_ready must be True in final response"
        )

        task_form = payload.get("task_form")
        assert task_form is not None, (
            "M2 contract: task_form must not be None when ready"
        )
        assert task_form.get("goal") is not None, (
            "M2 contract: task_form.goal required in ready response"
        )
        assert task_form.get("disease") is not None, (
            "M2 contract: task_form.disease required in ready response"
        )
        assert task_form.get("country") is not None, (
            "M2 contract: task_form.country required in ready response"
        )
        assert task_form.get("language") is not None, (
            "M2 contract: task_form.language required in ready response"
        )

        # M2 Extension: request_payload and task_form_payload for downstream integration
        assert "request_payload" in payload, (
            "M2 contract: request_payload field missing (for task persistence)"
        )
        assert "task_form_payload" in payload, (
            "M2 contract: task_form_payload field missing (for candidates/submit)"
        )

        request_payload = payload.get("request_payload")
        assert isinstance(request_payload, dict), (
            "M2 contract: request_payload must be dict with task_form_text"
        )
        assert "task_form_text" in request_payload, (
            "M2 contract: request_payload.task_form_text required"
        )

        task_form_payload = payload.get("task_form_payload")
        assert isinstance(task_form_payload, dict), (
            "M2 contract: task_form_payload must be dict"
        )
        assert "target" in task_form_payload or "goal" in task_form_payload, (
            "M2 contract: task_form_payload must include target/goal"
        )
        assert "disease" in task_form_payload, (
            "M2 contract: task_form_payload must include disease"
        )
