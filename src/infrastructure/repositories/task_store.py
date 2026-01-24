"""Simple in-memory task store for FastAPI facade.

This repository is intentionally lightweight to avoid coupling
API surface with pipeline internals. In production, replace
with persistent storage and real pipeline orchestration.
"""
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from typing import Dict, Optional
from uuid import uuid4

from src.presentation.schemas import InputType, TaskStatus, ProcessingStage


@dataclass
class TaskRecord:
    """Represents a task lifecycle for the API facade."""

    task_id: str
    input_type: InputType
    value: str
    project_tag: Optional[str]
    status: TaskStatus = TaskStatus.ACCEPTED
    stage: ProcessingStage = ProcessingStage.ACCEPTED
    results: Optional[dict] = None
    error: Optional[str] = None
    normalized_variant: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def update(self, **kwargs) -> None:
        """Update fields while bumping the timestamp."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = datetime.utcnow()


class InMemoryTaskStore:
    """Thread-safe in-memory task repository."""

    def __init__(self):
        self._tasks: Dict[str, TaskRecord] = {}
        self._lock = Lock()

    def create(self, input_type: InputType, value: str, project_tag: Optional[str]) -> TaskRecord:
        """Create a task record and store it."""
        task_id = f"task_{uuid4().hex[:8]}"
        record = TaskRecord(
            task_id=task_id,
            input_type=input_type,
            value=value,
            project_tag=project_tag,
        )
        with self._lock:
            self._tasks[task_id] = record
        return record

    def get(self, task_id: str) -> Optional[TaskRecord]:
        """Retrieve a task by id."""
        with self._lock:
            return self._tasks.get(task_id)

    def update(self, task_id: str, **kwargs) -> Optional[TaskRecord]:
        """Update a task in place."""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None
            task.update(**kwargs)
            return task

    def list_by_variant(self, normalized_variant: str) -> Dict[str, TaskRecord]:
        """Return tasks matching normalized variant."""
        with self._lock:
            return {
                task_id: record
                for task_id, record in self._tasks.items()
                if record.normalized_variant == normalized_variant
            }

    def all(self) -> Dict[str, TaskRecord]:
        """Return a copy of all tasks (primarily for diagnostics)."""
        with self._lock:
            return dict(self._tasks)

    def list_all(self) -> Dict[str, TaskRecord]:
        """Alias for all() to satisfy test expectations."""
        return self.all()
