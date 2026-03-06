from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Mapping, Optional


class TaskStatus(str, Enum):
    pending = "PENDING"
    started = "STARTED"
    success = "SUCCESS"
    failure = "FAILURE"
    retry = "RETRY"
    revoked = "REVOKED"

    @classmethod
    def from_celery(cls, status: str) -> "TaskStatus":
        try:
            return cls(status)
        except ValueError:
            return cls.pending


class WorkflowStatus(str, Enum):
    pending = "PENDING"
    processing_literature = "PROCESSING_LITERATURE"
    processing_pdf = "PROCESSING_PDF"
    translating = "TRANSLATING"
    extracting_evidence = "EXTRACTING_EVIDENCE"
    classifying = "CLASSIFYING"
    adjudicating = "ADJUDICATING"
    completed = "COMPLETED"
    failed = "FAILED"


WORKFLOW_STATUS_DESCRIPTIONS: Dict[WorkflowStatus, str] = {
    WorkflowStatus.pending: "Task accepted and waiting for execution.",
    WorkflowStatus.processing_literature: "Acquiring literature from upload/PubMed sources.",
    WorkflowStatus.processing_pdf: "Parsing uploaded document content.",
    WorkflowStatus.translating: "Translating non-English content into English.",
    WorkflowStatus.extracting_evidence: "Extracting entities, relations, and PS3/BS3 evidence.",
    WorkflowStatus.classifying: "Applying ACMG PS3/BS3 classification rules.",
    WorkflowStatus.adjudicating: "Resolving evidence conflicts with adjudication logic.",
    WorkflowStatus.completed: "Workflow completed successfully.",
    WorkflowStatus.failed: "Workflow terminated due to unrecoverable error.",
}


WORKFLOW_STATUS_TRANSITIONS: Dict[WorkflowStatus, tuple[WorkflowStatus, ...]] = {
    WorkflowStatus.pending: (
        WorkflowStatus.processing_literature,
        WorkflowStatus.processing_pdf,
        WorkflowStatus.failed,
    ),
    WorkflowStatus.processing_literature: (
        WorkflowStatus.processing_pdf,
        WorkflowStatus.translating,
        WorkflowStatus.extracting_evidence,
        WorkflowStatus.failed,
    ),
    WorkflowStatus.processing_pdf: (
        WorkflowStatus.translating,
        WorkflowStatus.extracting_evidence,
        WorkflowStatus.failed,
    ),
    WorkflowStatus.translating: (
        WorkflowStatus.extracting_evidence,
        WorkflowStatus.failed,
    ),
    WorkflowStatus.extracting_evidence: (
        WorkflowStatus.classifying,
        WorkflowStatus.adjudicating,
        WorkflowStatus.failed,
    ),
    WorkflowStatus.classifying: (
        WorkflowStatus.adjudicating,
        WorkflowStatus.completed,
        WorkflowStatus.failed,
    ),
    WorkflowStatus.adjudicating: (
        WorkflowStatus.completed,
        WorkflowStatus.failed,
    ),
    WorkflowStatus.completed: (),
    WorkflowStatus.failed: (
        WorkflowStatus.processing_literature,
        WorkflowStatus.processing_pdf,
    ),
}


class ProcessingStepStatus(str, Enum):
    pending = "PENDING"
    running = "RUNNING"
    completed = "COMPLETED"
    failed = "FAILED"
    skipped = "SKIPPED"


PROCESSING_STEP_ORDER: tuple[str, ...] = (
    "acquisition",
    "parsing",
    "translation",
    "extraction",
    "classification",
    "adjudication",
)


PROCESSING_NODE_TO_STEP: Dict[str, str] = {
    "acquisition": "acquisition",
    "parsing": "parsing",
    "translation": "translation",
    "extraction": "extraction",
    "acmg": "classification",
    "classification": "classification",
    "adjudication": "adjudication",
}


STEP_TO_WORKFLOW_STATUS: Dict[str, WorkflowStatus] = {
    "acquisition": WorkflowStatus.processing_literature,
    "parsing": WorkflowStatus.processing_pdf,
    "translation": WorkflowStatus.translating,
    "extraction": WorkflowStatus.extracting_evidence,
    "classification": WorkflowStatus.classifying,
    "adjudication": WorkflowStatus.adjudicating,
}


def can_transition_workflow_status(current: WorkflowStatus, next_status: WorkflowStatus) -> bool:
    return next_status in WORKFLOW_STATUS_TRANSITIONS.get(current, ())


def workflow_status_description(status: WorkflowStatus) -> str:
    return WORKFLOW_STATUS_DESCRIPTIONS.get(status, "")


def coerce_workflow_status(
    value: Any, default: WorkflowStatus = WorkflowStatus.pending
) -> WorkflowStatus:
    if isinstance(value, WorkflowStatus):
        return value
    if isinstance(value, str):
        normalized = value.strip().upper()
        for candidate in WorkflowStatus:
            if candidate.value == normalized:
                return candidate
    return default


def _coerce_processing_step_status(value: Any) -> ProcessingStepStatus:
    if isinstance(value, ProcessingStepStatus):
        return value
    if isinstance(value, str):
        normalized = value.strip().upper()
        for candidate in ProcessingStepStatus:
            if candidate.value == normalized:
                return candidate
    return ProcessingStepStatus.pending


def default_processing_steps(now: Optional[datetime] = None) -> Dict[str, Dict[str, Any]]:
    timestamp = (now or datetime.now(timezone.utc)).isoformat()
    return {
        step: {
            "status": ProcessingStepStatus.pending.value,
            "updated_at": timestamp,
            "message": None,
            "error_code": None,
        }
        for step in PROCESSING_STEP_ORDER
    }


def normalize_processing_steps(
    raw_steps: Any,
    *,
    node_trace: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Dict[str, Any]]:
    normalized = default_processing_steps()

    if isinstance(raw_steps, Mapping):
        for raw_key, raw_value in raw_steps.items():
            step = PROCESSING_NODE_TO_STEP.get(str(raw_key).lower(), str(raw_key).lower())
            if step not in normalized:
                continue

            if isinstance(raw_value, Mapping):
                status = _coerce_processing_step_status(raw_value.get("status"))
                normalized[step]["status"] = status.value
                normalized[step]["updated_at"] = (
                    raw_value.get("updated_at") or normalized[step]["updated_at"]
                )
                normalized[step]["message"] = raw_value.get("message")
                normalized[step]["error_code"] = raw_value.get("error_code")
            else:
                normalized[step]["status"] = _coerce_processing_step_status(raw_value).value

    if isinstance(node_trace, Mapping):
        for raw_node, outcome in node_trace.items():
            step = PROCESSING_NODE_TO_STEP.get(str(raw_node).lower())
            if not step or step not in normalized:
                continue
            if normalized[step]["status"] != ProcessingStepStatus.pending.value:
                continue
            outcome_text = str(outcome).strip().lower()
            if "fail" in outcome_text:
                normalized[step]["status"] = ProcessingStepStatus.failed.value
            elif "skip" in outcome_text or "fallback" in outcome_text:
                normalized[step]["status"] = ProcessingStepStatus.skipped.value
            elif "success" in outcome_text:
                normalized[step]["status"] = ProcessingStepStatus.completed.value

    return normalized


def merge_processing_step_update(
    processing_steps: Any,
    *,
    step: str,
    status: ProcessingStepStatus,
    message: Optional[str] = None,
    error_code: Optional[str] = None,
    timestamp: Optional[datetime] = None,
) -> Dict[str, Dict[str, Any]]:
    normalized = normalize_processing_steps(processing_steps)
    canonical_step = PROCESSING_NODE_TO_STEP.get(step.lower(), step.lower())
    if canonical_step not in normalized:
        return normalized
    normalized[canonical_step] = {
        "status": status.value,
        "updated_at": (timestamp or datetime.now(timezone.utc)).isoformat(),
        "message": message,
        "error_code": error_code,
    }
    return normalized


def calculate_progress_percentage(processing_steps: Any) -> float:
    normalized = normalize_processing_steps(processing_steps)
    total = len(PROCESSING_STEP_ORDER)
    if total == 0:
        return 0.0

    completed = 0
    for step in PROCESSING_STEP_ORDER:
        step_status = _coerce_processing_step_status(normalized[step].get("status"))
        if step_status in (ProcessingStepStatus.completed, ProcessingStepStatus.skipped):
            completed += 1

    return round((completed / total) * 100.0, 2)


def derive_workflow_status(
    processing_steps: Any,
    fallback: WorkflowStatus = WorkflowStatus.pending,
) -> WorkflowStatus:
    normalized = normalize_processing_steps(processing_steps)

    for step in PROCESSING_STEP_ORDER:
        status = _coerce_processing_step_status(normalized[step].get("status"))
        if status == ProcessingStepStatus.failed:
            return WorkflowStatus.failed

    if all(
        _coerce_processing_step_status(normalized[step].get("status"))
        in (ProcessingStepStatus.completed, ProcessingStepStatus.skipped)
        for step in PROCESSING_STEP_ORDER
    ):
        return WorkflowStatus.completed

    for step in PROCESSING_STEP_ORDER:
        status = _coerce_processing_step_status(normalized[step].get("status"))
        if status == ProcessingStepStatus.running:
            return STEP_TO_WORKFLOW_STATUS.get(step, fallback)

    return fallback
