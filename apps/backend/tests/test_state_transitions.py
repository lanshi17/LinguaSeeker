from __future__ import annotations

import ast
import inspect
import textwrap

from src.infrastructure.models import PaperTask
from src.infrastructure.postgres import PostgresClient
from src.services.enum import (
    PROCESSING_STEP_ORDER,
    ProcessingStepStatus,
    WorkflowStatus,
    can_transition_workflow_status,
    default_processing_steps,
    derive_workflow_status,
    merge_processing_step_update,
    normalize_processing_steps,
)


class TestPaperTaskDefaults:
    def test_paper_task_defaults_are_documented(self) -> None:
        assert PaperTask.__table__.c.status.default.arg == "queued"
        assert PaperTask.__table__.c.workflow_status.default.arg == "PENDING"
        assert PaperTask.__table__.c.fulltext_unavailable.default.arg == "false"
        assert PaperTask.__table__.c.processing_steps.nullable is True

    def test_create_paper_task_signature_defaults_match_model(self) -> None:
        signature = inspect.signature(PostgresClient.create_paper_task)

        assert signature.parameters["status"].default == "queued"
        assert signature.parameters["workflow_status"].default == "PENDING"
        assert signature.parameters["fulltext_unavailable"].default == "false"


class TestWorkflowStatusTransitions:
    def test_valid_workflow_transitions(self) -> None:
        assert can_transition_workflow_status(WorkflowStatus.pending, WorkflowStatus.processing_pdf)
        assert can_transition_workflow_status(
            WorkflowStatus.processing_pdf, WorkflowStatus.translating
        )
        assert can_transition_workflow_status(
            WorkflowStatus.translating, WorkflowStatus.extracting_evidence
        )
        assert can_transition_workflow_status(
            WorkflowStatus.extracting_evidence, WorkflowStatus.classifying
        )
        assert can_transition_workflow_status(WorkflowStatus.classifying, WorkflowStatus.completed)
        assert can_transition_workflow_status(WorkflowStatus.failed, WorkflowStatus.processing_pdf)

    def test_invalid_workflow_transitions(self) -> None:
        assert not can_transition_workflow_status(
            WorkflowStatus.completed, WorkflowStatus.classifying
        )
        assert not can_transition_workflow_status(
            WorkflowStatus.processing_pdf, WorkflowStatus.pending
        )
        assert not can_transition_workflow_status(WorkflowStatus.completed, WorkflowStatus.failed)


class TestProcessingStepTransitions:
    def test_processing_step_order_is_locked_to_v1_six_node_contract(self) -> None:
        assert PROCESSING_STEP_ORDER == (
            "acquisition",
            "parsing",
            "translation",
            "extraction",
            "classification",
            "adjudication",
        )

    def test_processing_steps_default_to_pending(self) -> None:
        processing_steps = default_processing_steps()

        assert set(processing_steps) == set(PROCESSING_STEP_ORDER)
        assert {step["status"] for step in processing_steps.values()} == {
            ProcessingStepStatus.pending.value
        }

    def test_processing_step_lifecycle_running_then_completed(self) -> None:
        processing_steps = default_processing_steps()
        processing_steps = merge_processing_step_update(
            processing_steps,
            step="parsing",
            status=ProcessingStepStatus.running,
            message="Parsing started",
        )

        assert processing_steps["parsing"]["status"] == ProcessingStepStatus.running.value
        assert derive_workflow_status(processing_steps) == WorkflowStatus.processing_pdf

        processing_steps = merge_processing_step_update(
            processing_steps,
            step="parsing",
            status=ProcessingStepStatus.completed,
            message="Parsing finished",
        )

        assert processing_steps["parsing"]["status"] == ProcessingStepStatus.completed.value

    def test_processing_step_lifecycle_running_then_failed(self) -> None:
        processing_steps = default_processing_steps()
        processing_steps = merge_processing_step_update(
            processing_steps,
            step="translation",
            status=ProcessingStepStatus.running,
        )
        processing_steps = merge_processing_step_update(
            processing_steps,
            step="translation",
            status=ProcessingStepStatus.failed,
            error_code="TRANSLATION_ERROR",
        )

        assert processing_steps["translation"]["status"] == ProcessingStepStatus.failed.value
        assert processing_steps["translation"]["error_code"] == "TRANSLATION_ERROR"
        assert derive_workflow_status(processing_steps) == WorkflowStatus.failed

    def test_processing_step_lifecycle_pending_to_skipped_via_node_trace(self) -> None:
        normalized = normalize_processing_steps(
            None,
            node_trace={
                "acquisition": "fallback_metadata_abstract",
                "translation": "skipped_english",
                "acmg": "success",
            },
        )

        assert normalized["acquisition"]["status"] == ProcessingStepStatus.skipped.value
        assert normalized["translation"]["status"] == ProcessingStepStatus.skipped.value
        assert normalized["classification"]["status"] == ProcessingStepStatus.completed.value

    def test_normalize_processing_steps_drops_legacy_reasoning_entry(self) -> None:
        normalized = normalize_processing_steps(
            {
                "reasoning": {
                    "status": "COMPLETED",
                    "updated_at": "2026-03-30T00:00:00+00:00",
                    "message": "Legacy reasoning step",
                    "error_code": None,
                },
                "classification": {"status": "RUNNING"},
            }
        )

        assert set(normalized) == set(PROCESSING_STEP_ORDER)
        assert "reasoning" not in normalized
        assert normalized["classification"]["status"] == ProcessingStepStatus.running.value


class TestCreateEvidenceRecordIdempotency:
    def test_document_non_idempotent_insert_path(self) -> None:
        source = textwrap.dedent(inspect.getsource(PostgresClient.create_evidence_record))
        tree = ast.parse(source)
        call_names = [
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        ]

        assert "add" in call_names
        assert "flush" in call_names
        assert "merge" not in call_names
        assert "filter" not in call_names
