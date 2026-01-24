"""Presentation layer services for the FastAPI facade.

These services handle API-specific logic and data transformation.
"""
from typing import Optional, Dict, List

from src.infrastructure.repositories.task_store import InMemoryTaskStore, TaskRecord
from src.presentation.schemas import (
    EvidenceLevel,
    InputType,
    Language,
    ProcessingStage,
    TaskResultData,
    TaskStatus,
)
from src.presentation.errors import BadRequestError, NotFoundError, InvalidHGVSError


def _normalize_variant(variant: str) -> str:
    """Normalize HGVS string for consistent matching."""
    return variant.strip().replace(" ", "").upper()


class TaskService:
    """Handles task lifecycle operations."""

    def __init__(self, store: InMemoryTaskStore):
        self.store = store

    async def create_task(self, input_type: InputType, value: str, project_tag: Optional[str]) -> str:
        """Create a task and stub-complete it for demo purposes."""
        self._validate_input(input_type, value)
        record = self.store.create(input_type=input_type, value=value, project_tag=project_tag)
        # Immediately mark as completed with placeholder outputs to enable downstream fetches.
        self._complete_task(record.task_id)
        return record.task_id

    def _validate_input(self, input_type: InputType, value: str) -> None:
        if input_type == InputType.PMID and not value.isdigit():
            raise BadRequestError("PMID must be numeric", error="invalid_pmid")
        if input_type == InputType.DOI and not value.startswith("10."):
            raise BadRequestError("Invalid DOI format", error="invalid_doi")
        if not value:
            raise BadRequestError("Value cannot be empty", error="missing_value")

    def _complete_task(self, task_id: str) -> None:
        sample_result = {
            "detected_language": "zh",
            "ps3_evidence_level": EvidenceLevel.PS3_SUPPORTING,
            "arbiter_score": 85,
            "odds_path": None,
            "p1_source": "not reported",
            "html_highlight_url": f"/api/v1/tasks/{task_id}/highlighted.html",
            "structured_result_url": f"/api/v1/tasks/{task_id}/result.json",
            "normalized_variant": _normalize_variant("NM_000546.5(TP53):c.722C>T"),
            "pmid": "35121234",
            "doi": "10.1038/s41436-022-01456-w",
        }
        updated = self.store.update(
            task_id,
            status=TaskStatus.SUCCESS,
            stage=ProcessingStage.COMPLETE,
            results=sample_result,
            normalized_variant=sample_result["normalized_variant"],
        )
        if not updated:
            raise NotFoundError(f"Task not found: {task_id}")

    def get_task_status(self, task_id: str) -> Dict:
        record = self.store.get(task_id)
        if not record:
            raise NotFoundError(f"Task not found: {task_id}")
        return {
            "task_id": record.task_id,
            "status": record.status,
            "stage": record.stage,
            "results": TaskResultData(**record.results) if record.results else None,
            "error": record.error,
        }

    async def get_task_result(self, task_id: str) -> Dict:
        record = self.store.get(task_id)
        if not record:
            raise NotFoundError(f"Task not found: {task_id}")
        if record.status != TaskStatus.SUCCESS:
            raise NotFoundError(f"Task {task_id} has not completed", error="task_not_ready")
        return record.results or {}

    def get_highlighted_html(self, task_id: str) -> str:
        record = self.store.get(task_id)
        if not record:
            raise NotFoundError(f"Task not found: {task_id}")
        if record.status != TaskStatus.SUCCESS:
            raise NotFoundError(f"Task {task_id} has not completed", error="task_not_ready")

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Highlighted Document - {task_id}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 24px; }}
                .container {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
                .column {{ border: 1px solid #ddd; padding: 16px; border-radius: 8px; background: #fafafa; }}
                .highlight {{ background-color: #fff59d; }}
            </style>
        </head>
        <body>
            <h1>Document Highlighting</h1>
            <div class="container">
                <div class="column">
                    <h2>Original</h2>
                    <p>Original content for {task_id}...</p>
                </div>
                <div class="column">
                    <h2>English</h2>
                    <p>English translation with <span class="highlight">highlighted evidence</span>...</p>
                </div>
            </div>
        </body>
        </html>
        """


class EvidenceQueryService:
    """Query evidence records aggregated from tasks."""

    def __init__(self, store: InMemoryTaskStore):
        self.store = store

    def query_evidence(
        self,
        variant: str,
        evidence_level: Optional[EvidenceLevel] = None,
        min_score: Optional[int] = None,
    ) -> List[Dict]:
        normalized = _normalize_variant(variant)
        if not normalized:
            raise InvalidHGVSError(variant)

        candidates = self.store.list_by_variant(normalized).values()
        matches: List[Dict] = []
        for task in candidates:
            result = task.results or {}
            level = result.get("ps3_evidence_level")
            score = result.get("arbiter_score")
            if evidence_level and level != evidence_level:
                continue
            if min_score is not None and score is not None and score < min_score:
                continue
            matches.append(
                {
                    "task_id": task.task_id,
                    "pmid": result.get("pmid"),
                    "doi": result.get("doi"),
                    "detected_language": result.get("detected_language"),
                    "ps3_evidence_level": level,
                    "arbiter_score": score or 0,
                    "odds_path": result.get("odds_path"),
                    "html_highlight_url": result.get("html_highlight_url"),
                }
            )
        return matches


class MetadataService:
    """Expose metadata enumerations for clients."""

    @staticmethod
    def get_supported_languages() -> List[str]:
        return [member.value for member in Language]

    @staticmethod
    def get_evidence_levels() -> List[str]:
        return [member.value for member in EvidenceLevel]


# Shared instances for router wiring
_task_store = InMemoryTaskStore()
task_service = TaskService(_task_store)
evidence_query_service = EvidenceQueryService(_task_store)
metadata_service = MetadataService()
