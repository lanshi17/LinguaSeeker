"""Parsing Task domain entity.

Represents an asynchronous document processing task.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4


class TaskStatus(str, Enum):
    """Task execution status."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRY = "RETRY"


class TaskStage(str, Enum):
    """Task processing stages."""

    INGESTION = "INGESTION"
    DECOMPOSITION = "DECOMPOSITION"
    LAYOUT = "LAYOUT"
    TRANSLATION = "TRANSLATION"
    EVIDENCE = "EVIDENCE"
    ARBITRATION = "ARBITRATION"
    COMPLETED = "COMPLETED"


@dataclass
class ParsingTask:
    """Domain entity representing an asynchronous parsing task.

    Manages task lifecycle, retry logic, and progress tracking.
    """

    # Constants
    MAX_RETRIES: int = field(default=3, init=False, repr=False)
    DEFAULT_PRIORITY: int = field(default=5, init=False, repr=False)

    id: UUID = field(default_factory=uuid4)
    document_id: UUID = field(default_factory=uuid4)
    current_stage: TaskStage = TaskStage.INGESTION
    progress_percentage: int = 0
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 5
    retry_count: int = 0
    failure_reason: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    estimated_completion: Optional[datetime] = None

    def __post_init__(self) -> None:
        """Validate task after initialization."""
        self._validate()

    def _validate(self) -> None:
        """Validate task invariants."""
        if not (0 <= self.progress_percentage <= 100):
            raise ValueError(
                f"Progress percentage {self.progress_percentage} must be between 0 and 100"
            )

        if not (0 <= self.priority <= 10):
            raise ValueError(f"Priority {self.priority} must be between 0 and 10")

        if self.retry_count < 0:
            raise ValueError("Retry count must be non-negative")

        if self.retry_count > self.MAX_RETRIES:
            raise ValueError(
                f"Retry count {self.retry_count} exceeds maximum {self.MAX_RETRIES}"
            )

    def start(self) -> None:
        """Start task processing."""
        if self.status not in [TaskStatus.PENDING, TaskStatus.RETRY]:
            raise ValueError(
                f"Cannot start task in status {self.status}"
            )

        self.status = TaskStatus.PROCESSING
        self.started_at = datetime.utcnow()
        self._estimate_completion()

    def advance_stage(self, new_stage: TaskStage) -> None:
        """Advance to next processing stage."""
        if self.status != TaskStatus.PROCESSING:
            raise ValueError(
                f"Cannot advance stage for task in status {self.status}"
            )

        self.current_stage = new_stage
        self._update_progress_from_stage(new_stage)
        self._estimate_completion()

    def _update_progress_from_stage(self, stage: TaskStage) -> None:
        """Update progress percentage based on stage."""
        stage_progress = {
            TaskStage.INGESTION: 10,
            TaskStage.DECOMPOSITION: 20,
            TaskStage.LAYOUT: 40,
            TaskStage.TRANSLATION: 60,
            TaskStage.EVIDENCE: 80,
            TaskStage.ARBITRATION: 90,
            TaskStage.COMPLETED: 100,
        }
        self.progress_percentage = stage_progress.get(stage, self.progress_percentage)

    def update_progress(self, percentage: int) -> None:
        """Update progress percentage."""
        if not (0 <= percentage <= 100):
            raise ValueError(f"Progress percentage {percentage} must be between 0 and 100")

        if percentage < self.progress_percentage:
            raise ValueError("Progress cannot go backwards")

        self.progress_percentage = percentage
        self._estimate_completion()

    def complete(self) -> None:
        """Mark task as completed."""
        if self.status != TaskStatus.PROCESSING:
            raise ValueError(
                f"Cannot complete task in status {self.status}"
            )

        self.status = TaskStatus.COMPLETED
        self.current_stage = TaskStage.COMPLETED
        self.progress_percentage = 100
        self.completed_at = datetime.utcnow()
        self.estimated_completion = None

    def fail(self, reason: str) -> None:
        """Mark task as failed."""
        if not reason:
            raise ValueError("Failure reason is required")

        if self.status not in [TaskStatus.PENDING, TaskStatus.PROCESSING, TaskStatus.RETRY]:
            raise ValueError(
                f"Cannot fail task in status {self.status}"
            )

        self.status = TaskStatus.FAILED
        self.failure_reason = reason
        self.completed_at = datetime.utcnow()
        self.estimated_completion = None

    def retry(self) -> None:
        """Retry failed task."""
        if self.status != TaskStatus.FAILED:
            raise ValueError(
                f"Cannot retry task in status {self.status}"
            )

        if self.retry_count >= self.MAX_RETRIES:
            raise ValueError(
                f"Maximum retries ({self.MAX_RETRIES}) exceeded"
            )

        self.retry_count += 1
        self.status = TaskStatus.RETRY
        self.failure_reason = None
        self.completed_at = None

    def increase_priority(self) -> None:
        """Increase task priority (manual escalation)."""
        if self.priority < 10:
            self.priority += 1

    def decrease_priority(self) -> None:
        """Decrease task priority."""
        if self.priority > 0:
            self.priority -= 1

    def _estimate_completion(self) -> None:
        """Estimate completion time based on progress and elapsed time."""
        if self.status != TaskStatus.PROCESSING or not self.started_at:
            return

        if self.progress_percentage == 0:
            # Default estimate: 5 minutes for average document
            self.estimated_completion = self.started_at + timedelta(minutes=5)
            return

        elapsed = datetime.utcnow() - self.started_at
        total_estimated = elapsed / (self.progress_percentage / 100)
        self.estimated_completion = self.started_at + total_estimated

    def is_terminal(self) -> bool:
        """Check if task is in terminal state."""
        return self.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]

    def is_running(self) -> bool:
        """Check if task is currently running."""
        return self.status == TaskStatus.PROCESSING

    def can_retry(self) -> bool:
        """Check if task can be retried."""
        return self.status == TaskStatus.FAILED and self.retry_count < self.MAX_RETRIES

    def get_elapsed_time(self) -> Optional[timedelta]:
        """Get elapsed processing time."""
        if not self.started_at:
            return None

        end_time = self.completed_at or datetime.utcnow()
        return end_time - self.started_at

    def __repr__(self) -> str:
        """String representation of task."""
        return (
            f"ParsingTask(id={self.id}, status={self.status}, "
            f"stage={self.current_stage}, progress={self.progress_percentage}%)"
        )
