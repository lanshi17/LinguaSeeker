from __future__ import annotations

from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch

import pytest

from src.state.global_state import SupervisorState
from src.utils.exceptions import ValidationException


def _base_state(**overrides) -> SupervisorState:
    defaults: dict = {
        "request_id": "req-001",
        "paper_task_id": 1,
        "document_id": 10,
        "celery_task_id": "celery-001",
        "source": "upload",
        "file_paths": [],
        "urls": [],
        "pmids": [],
        "current_node": "",
        "workflow_status": "running",
        "processing_steps": {},
        "node_trace": {},
        "retries": {},
        "warnings": [],
        "errors": [],
        "requires_human_review": False,
        "parsing_result": None,
        "parser_backend": None,
        "markdown_content": None,
        "image_paths": [],
        "sentence_alignments": None,
        "translated_markdown": None,
        "image_descriptions": None,
        "evidence_output": None,
        "extracted_fields": None,
        "arbitration_confidence": None,
        "final_evidence_strength": None,
        "acmg_result": None,
        "evidence_sources": [],
        "output_files": None,
        "final_result": None,
        "_inner_processing_state": None,
    }
    defaults.update(overrides)
    return cast(SupervisorState, cast(object, defaults))


class TestAcquisitionNode:
    def test_upload_missing_files_raises(self, tmp_path: Path):
        from src.agents.acquisition.node import run_acquisition_node

        state = _base_state(
            source="upload",
            file_paths=[str(tmp_path / "does_not_exist.pdf")],
        )
        with pytest.raises(ValidationException, match="Files not found"):
            run_acquisition_node(state)

    def test_upload_existing_files_succeeds(self, tmp_path: Path):
        from src.agents.acquisition.node import run_acquisition_node

        f = tmp_path / "ok.pdf"
        f.write_text("data")
        state = _base_state(source="upload", file_paths=[str(f)])
        result = run_acquisition_node(state)
        assert result["current_node"] == "acquisition"

    def test_upload_empty_file_paths_succeeds(self):
        from src.agents.acquisition.node import run_acquisition_node

        state = _base_state(source="upload", file_paths=[])
        result = run_acquisition_node(state)
        assert result["current_node"] == "acquisition"

    def test_unsupported_source_raises(self):
        from src.agents.acquisition.node import run_acquisition_node

        state = _base_state(source="ftp")
        with pytest.raises(ValidationException, match="Unsupported"):
            run_acquisition_node(state)

    def test_pubmed_source_calls_agent(self, monkeypatch):
        from dataclasses import dataclass

        from src.agents.acquisition import node as acq_mod
        from src.agents.acquisition.node import run_acquisition_node

        @dataclass
        class FakePlanItem:
            normalized_value: str

        agent = MagicMock()
        agent.plan_pubmed_request.return_value = [FakePlanItem("PM123")]
        factory = MagicMock(return_value=agent)
        monkeypatch.setattr(acq_mod, "get_literature_acquisition_agent", factory)

        state = _base_state(source="pubmed", pmids=["PM123"])
        result = run_acquisition_node(state)
        agent.plan_pubmed_request.assert_called_once()
        assert result["current_node"] == "acquisition"

    def test_web_source_calls_agent(self, monkeypatch):
        from dataclasses import dataclass

        from src.agents.acquisition import node as acq_mod
        from src.agents.acquisition.node import run_acquisition_node

        @dataclass
        class FakePlanItem:
            normalized_value: str

        agent = MagicMock()
        agent.plan_web_request.return_value = [FakePlanItem("https://example.com")]
        factory = MagicMock(return_value=agent)
        monkeypatch.setattr(acq_mod, "get_literature_acquisition_agent", factory)

        state = _base_state(source="web", urls=["https://example.com"])
        result = run_acquisition_node(state)
        agent.plan_web_request.assert_called_once()
        assert result["current_node"] == "acquisition"


class TestParsingNode:
    def test_no_file_paths_returns_early(self):
        from src.agents.parsing.node import run_parsing_node

        state = _base_state(file_paths=[])
        result = run_parsing_node(state)
        assert result.get("parsing_result") is None

    def test_parse_success_sets_fields(self, monkeypatch):
        from src.agents.parsing import node as parse_mod
        from src.agents.parsing.node import run_parsing_node

        mock_result = MagicMock()
        mock_result.model_dump.return_value = {"ok": True}
        mock_result.parser_backend = "mineru"
        mock_result.markdown_content = "# Hello"
        mock_result.image_paths = ["/tmp/img.png"]

        mock_agent = MagicMock()
        mock_agent.parse_documents.return_value = mock_result
        factory = MagicMock(return_value=mock_agent)
        monkeypatch.setattr(parse_mod, "get_document_parsing_agent", factory)

        state = _base_state(file_paths=["/some/file.pdf"])
        result = run_parsing_node(state)
        assert result["parsing_result"] == {"ok": True}
        assert result["parser_backend"] == "mineru"
        assert result["markdown_content"] == "# Hello"
        assert result["image_paths"] == ["/tmp/img.png"]

    def test_parse_returns_empty_markdown(self, monkeypatch):
        from src.agents.parsing import node as parse_mod
        from src.agents.parsing.node import run_parsing_node

        mock_result = MagicMock()
        mock_result.model_dump.return_value = {"ok": True}
        mock_result.parser_backend = "mineru"
        mock_result.markdown_content = ""
        mock_result.image_paths = []

        mock_agent = MagicMock()
        mock_agent.parse_documents.return_value = mock_result
        factory = MagicMock(return_value=mock_agent)
        monkeypatch.setattr(parse_mod, "get_document_parsing_agent", factory)

        state = _base_state(file_paths=["/some/file.pdf"])
        result = run_parsing_node(state)
        assert result["markdown_content"] == ""


class TestExtractionNode:
    def _mock_evidence_agent(self, monkeypatch):
        """Patch EvidenceAgent in extraction.node and return the mock."""
        from src.agents.extraction import node as ext_mod

        inner_state = {
            "ps3_evidence": {
                "ps3_step_4": {"final_evidence_strength": "strong"},
            },
        }
        mock_agent = MagicMock()
        mock_agent.extract_ps3_evidence_sync.return_value = inner_state
        mock_agent._extract_output_contract_fields.return_value = {
            "ps3_evidence": inner_state["ps3_evidence"],
            "extracted_fields": {},
            "evidence_sources": [],
            "field_confidence_scores": {},
            "overall_confidence": 0.9,
        }
        monkeypatch.setattr(ext_mod, "EvidenceAgent", MagicMock(return_value=mock_agent))
        return mock_agent

    def test_no_existing_evidence_output(self, monkeypatch):
        from src.agents.extraction.node import run_extraction_node

        self._mock_evidence_agent(monkeypatch)
        state = _base_state(evidence_output=None, markdown_content="# test")
        result = run_extraction_node(state)
        assert result["evidence_output"] is not None
        assert result["current_node"] == "extract_evidence"

    def test_with_existing_evidence_output(self, monkeypatch):
        from src.agents.extraction.node import run_extraction_node
        from src.domain.models import EvidenceOutput

        self._mock_evidence_agent(monkeypatch)
        existing = EvidenceOutput(ps3_evidence={"existing": True})
        state = _base_state(evidence_output=existing, markdown_content="# test")
        result = run_extraction_node(state)
        assert result["evidence_output"] is not None

    def test_missing_markdown_uses_empty_string(self, monkeypatch):
        from src.agents.extraction.node import run_extraction_node

        self._mock_evidence_agent(monkeypatch)
        state = _base_state(markdown_content=None)
        result = run_extraction_node(state)
        assert result["current_node"] == "extract_evidence"


class TestArbitrationNode:
    def _mock_arbitration_deps(self, monkeypatch, *, decision="approved"):
        from src.agents.arbitration import node as arb_mod

        inner_state = {
            "ps3_evidence": {
                "ps3_step_4": {"final_evidence_strength": "strong"},
            },
        }
        mock_agent = MagicMock()
        mock_agent.arbitrate_score.return_value = inner_state
        mock_agent.route_decision.return_value = decision
        monkeypatch.setattr(arb_mod, "EvidenceAgent", MagicMock(return_value=mock_agent))

        mock_classifier = MagicMock()
        mock_classifier.classify.return_value = MagicMock(
            overall_score=90.0,
            classification="pathogenic",
        )
        monkeypatch.setattr(arb_mod, "EvidenceClassifier", mock_classifier)
        return mock_agent

    def test_decision_approved(self, monkeypatch):
        from src.agents.arbitration.node import run_arbitration_node

        self._mock_arbitration_deps(monkeypatch, decision="approved")
        state = _base_state(evidence_output=None)
        result = run_arbitration_node(state)
        assert result["requires_human_review"] is False
        assert result["current_node"] == "arbitration"

    def test_decision_needs_review(self, monkeypatch):
        from src.agents.arbitration.node import run_arbitration_node

        self._mock_arbitration_deps(monkeypatch, decision="needs_review")
        state = _base_state(evidence_output=None)
        result = run_arbitration_node(state)
        assert result["requires_human_review"] is True

    def test_with_existing_evidence_output_calls_model_copy(self, monkeypatch):
        from src.agents.arbitration.node import run_arbitration_node
        from src.domain.models import EvidenceOutput

        self._mock_arbitration_deps(monkeypatch, decision="approved")
        existing = EvidenceOutput(ps3_evidence={"old": True})
        state = _base_state(evidence_output=existing)
        result = run_arbitration_node(state)
        assert result["evidence_output"] is not None

    def test_no_existing_evidence_output(self, monkeypatch):
        from src.agents.arbitration.node import run_arbitration_node

        self._mock_arbitration_deps(monkeypatch, decision="approved")
        state = _base_state(evidence_output=None)
        result = run_arbitration_node(state)
        assert result["acmg_result"] is not None


class TestInteractionNode:
    def test_no_input_returns_early(self):
        from src.agents.interaction.node import run_interaction_node

        state = _base_state()
        result = run_interaction_node(state)
        assert result.get("session_id") is None

    def test_start_interaction_with_user_input(self, monkeypatch):
        from src.agents.interaction import node as int_mod
        from src.agents.interaction.node import run_interaction_node

        mock_agent = MagicMock()
        monkeypatch.setattr(int_mod, "InteractionAgent", MagicMock(return_value=mock_agent))
        monkeypatch.setattr(
            "asyncio.run",
            lambda coro: {
                "session_id": "sess-1",
                "question": "What gene?",
                "task_form": {"goal": "classify", "disease": "cancer"},
                "ready": True,
            },
        )

        state = _base_state(user_input="classify BRCA1")
        result = run_interaction_node(state)
        assert result.get("session_id") == "sess-1"
        assert result.get("interaction_ready") is True
        assert result.get("goal") == "classify"
        assert result.get("disease") == "cancer"

    def test_respond_interaction_with_session(self, monkeypatch):
        from src.agents.interaction import node as int_mod
        from src.agents.interaction.node import run_interaction_node

        mock_agent = MagicMock()
        monkeypatch.setattr(int_mod, "InteractionAgent", MagicMock(return_value=mock_agent))
        monkeypatch.setattr(
            "asyncio.run",
            lambda coro: {
                "session_id": "sess-1",
                "question": None,
                "task_form": None,
                "ready": False,
            },
        )

        state = _base_state(session_id="sess-1", user_response="BRCA1")
        result = run_interaction_node(state)
        assert result.get("interaction_ready") is False
        assert result["requires_human_review"] is True

    def test_task_form_field_extraction(self, monkeypatch):
        from src.agents.interaction import node as int_mod
        from src.agents.interaction.node import run_interaction_node

        mock_agent = MagicMock()
        monkeypatch.setattr(int_mod, "InteractionAgent", MagicMock(return_value=mock_agent))
        monkeypatch.setattr(
            "asyncio.run",
            lambda coro: {
                "session_id": "s1",
                "question": "",
                "task_form": {
                    "goal": "PS3",
                    "disease": "Lung cancer",
                    "country": "CN",
                    "language": "zh",
                },
                "ready": True,
            },
        )

        state = _base_state(user_input="start")
        result = run_interaction_node(state)
        assert result.get("goal") == "PS3"
        assert result.get("disease") == "Lung cancer"
        assert result.get("country") == "CN"
        assert result.get("language") == "zh"


class TestSupervisorHelpers:
    def test_is_low_confidence_none(self):
        from src.agents.supervisor import _is_low_confidence

        assert _is_low_confidence(None) is False

    def test_is_low_confidence_zero(self):
        from src.agents.supervisor import _is_low_confidence

        assert _is_low_confidence(0) is True

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (0.84, True),
            (0.85, False),
            (0.86, False),
            (84.9, True),
            (85.0, False),
            (85.1, False),
        ],
    )
    def test_is_low_confidence_thresholds(self, value, expected):
        from src.agents.supervisor import _is_low_confidence

        assert _is_low_confidence(value) is expected

    def test_to_float_int(self):
        from src.agents.supervisor import _to_float

        assert _to_float(5) == 5.0

    def test_to_float_float(self):
        from src.agents.supervisor import _to_float

        assert _to_float(3.14) == 3.14

    def test_to_float_str(self):
        from src.agents.supervisor import _to_float

        assert _to_float("0.5") == 0.5

    def test_to_float_str_percent(self):
        from src.agents.supervisor import _to_float

        assert _to_float("85%") == 85.0

    def test_to_float_empty_string(self):
        from src.agents.supervisor import _to_float

        assert _to_float("") is None

    def test_to_float_none(self):
        from src.agents.supervisor import _to_float

        assert _to_float(None) is None

    def test_to_float_bad_string(self):
        from src.agents.supervisor import _to_float

        assert _to_float("abc") is None
