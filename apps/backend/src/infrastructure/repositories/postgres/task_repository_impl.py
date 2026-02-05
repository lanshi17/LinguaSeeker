"""PostgreSQL implementation of Task Repository.

Manages parsing task persistence and querying.
"""

from typing import List, Optional, Union
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy import select, func, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.parsing_task import (
    ParsingTask,
    TaskStatus,
    TaskStage,
    TaskType,
    StageLabel,
    normalize_stage_label,
)
from src.infrastructure.database.postgres_models import (
    ParsingTask as TaskModel,
    TaskStatus as TaskStatusEnum,
    TaskStage as TaskStageEnum,
    TaskType as TaskTypeEnum,
)


class TaskRepositoryImpl:
    """PostgreSQL implementation of task repository."""

    def __init__(self, session: AsyncSession):
        """Initialize repository with database session."""
        self.session = session

    def _to_domain(self, model: TaskModel) -> ParsingTask:
        """Convert database model to domain entity."""
        return ParsingTask(
            id=model.id,
            document_id=model.document_id,
            task_type=TaskType(model.task_type.value) if model.task_type else TaskType.PDF_PARSE,
            current_stage=TaskStage(model.current_stage.value),
            progress_percentage=model.progress_percentage,
            status=TaskStatus(model.status.value),
            priority=model.priority,
            retry_count=model.retry_count,
            failure_reason=model.failure_reason,
            started_at=model.started_at,
            completed_at=model.completed_at,
            created_at=model.created_at,
            updated_at=model.updated_at if hasattr(model, 'updated_at') else model.created_at,
            estimated_completion=model.estimated_completion,
        )

    def _to_model(self, entity: ParsingTask) -> TaskModel:
        """Convert domain entity to database model."""
        return TaskModel(
            id=entity.id,
            document_id=entity.document_id,
            task_type=TaskTypeEnum(entity.task_type.value),
            current_stage=TaskStageEnum(entity.current_stage.value),
            progress_percentage=entity.progress_percentage,
            status=TaskStatusEnum(entity.status.value),
            priority=entity.priority,
            retry_count=entity.retry_count,
            failure_reason=entity.failure_reason,
            started_at=entity.started_at,
            completed_at=entity.completed_at,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            estimated_completion=entity.estimated_completion,
        )

    def _coerce_status_enum(self, status: Union[str, TaskStatus]) -> TaskStatusEnum:
        """Normalize status input into the Postgres enum."""
        if isinstance(status, TaskStatus):
            label = status.value
        else:
            label = str(status).upper()
        try:
            return TaskStatusEnum(label)
        except ValueError as exc:  # pragma: no cover - defensive
            raise ValueError(f"Unsupported task status '{status}'") from exc

    def _coerce_stage_enum(self, stage: StageLabel) -> TaskStageEnum:
        """Normalize stage labels into the Postgres enum."""
        normalized_stage = normalize_stage_label(stage)
        return TaskStageEnum(normalized_stage.value)

    async def save(self, task: ParsingTask) -> ParsingTask:
        """Save or update a task."""
        try:
            stmt = select(TaskModel).where(TaskModel.id == task.id)
            result = await self.session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing
                existing.current_stage = TaskStageEnum(task.current_stage.value)
                existing.progress_percentage = task.progress_percentage
                existing.status = TaskStatusEnum(task.status.value)
                existing.priority = task.priority
                existing.retry_count = task.retry_count
                existing.failure_reason = task.failure_reason
                existing.started_at = task.started_at
                existing.completed_at = task.completed_at
                existing.updated_at = datetime.utcnow()  # Update the timestamp when saving
                existing.estimated_completion = task.estimated_completion
                existing.task_type = TaskTypeEnum(task.task_type.value)
            else:
                # Create new
                model = self._to_model(task)
                self.session.add(model)

            await self.session.commit()
            await self.session.refresh(existing if existing else model)
            return self._to_domain(existing if existing else model)
        except Exception as e:
            # Rollback on error to prevent transaction abortion
            await self.session.rollback()
            raise e

    async def find_by_id(self, task_id: UUID) -> Optional[ParsingTask]:
        """Find task by ID."""
        stmt = select(TaskModel).where(TaskModel.id == task_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def get_by_id(self, task_id: str) -> Optional[ParsingTask]:
        """Get task by ID (alias for find_by_id to maintain compatibility)."""
        from uuid import UUID

        try:
            uuid_task_id = UUID(task_id)
            return await self.find_by_id(uuid_task_id)
        except ValueError:
            # Invalid UUID format
            return None

    async def find_by_document_id(self, document_id: UUID) -> Optional[ParsingTask]:
        """Find task by document ID."""
        stmt = select(TaskModel).where(TaskModel.document_id == document_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def find_by_status(
        self,
        status: TaskStatus,
        limit: int = 100,
        offset: int = 0,
        priority_filter: Optional[int] = None,
    ) -> List[ParsingTask]:
        """Find tasks by status."""
        stmt = (
            select(TaskModel)
            .where(TaskModel.status == TaskStatusEnum(status.value))
            .order_by(TaskModel.priority.desc(), TaskModel.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        if priority_filter is not None:
            stmt = stmt.where(TaskModel.priority >= priority_filter)
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return [self._to_domain(model) for model in models]

    async def find_pending_by_priority(self, limit: int = 10) -> List[ParsingTask]:
        """Find pending tasks ordered by priority."""
        stmt = (
            select(TaskModel)
            .where(TaskModel.status == TaskStatusEnum.PENDING)
            .order_by(TaskModel.priority.desc(), TaskModel.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return [self._to_domain(model) for model in models]

    async def find_failed_retryable(self, limit: int = 10) -> List[ParsingTask]:
        """Find failed tasks that can be retried."""
        stmt = (
            select(TaskModel)
            .where(
                TaskModel.status == TaskStatusEnum.FAILED,
                TaskModel.retry_count < 3  # MAX_RETRIES
            )
            .order_by(TaskModel.priority.desc(), TaskModel.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return [self._to_domain(model) for model in models]

    async def update_progress(
        self, task_id: UUID, progress: int, stage: Optional[TaskStage] = None
    ) -> bool:
        """Update task progress and optionally stage."""
        try:
            values = {"progress_percentage": progress}
            if stage:
                values["current_stage"] = TaskStageEnum(stage.value)

            stmt = update(TaskModel).where(TaskModel.id == task_id).values(**values)
            result = await self.session.execute(stmt)
            await self.session.commit()
            return result.rowcount > 0
        except Exception as e:
            # Rollback on error to prevent transaction abortion
            await self.session.rollback()
            raise e

    async def delete(self, task_id: UUID) -> bool:
        """Delete a task."""
        try:
            stmt = select(TaskModel).where(TaskModel.id == task_id)
            result = await self.session.execute(stmt)
            model = result.scalar_one_or_none()

            if model:
                await self.session.delete(model)
                await self.session.commit()
                return True
            return False
        except Exception as e:
            # Rollback on error to prevent transaction abortion
            await self.session.rollback()
            raise e

    async def update_status(
        self,
        task_id: UUID,
        status: Union[str, TaskStatus],
        progress: int,
        stage: StageLabel,
        error_message: Optional[str] = None,
    ) -> bool:
        """Update task status, progress, and stage."""
        try:
            stmt = select(TaskModel).where(TaskModel.id == task_id)
            result = await self.session.execute(stmt)
            model = result.scalar_one_or_none()

            if model:
                status_enum = self._coerce_status_enum(status)
                model.status = status_enum
                model.progress_percentage = progress
                model.current_stage = self._coerce_stage_enum(stage)
                if error_message is not None:
                    model.failure_reason = error_message
                elif status_enum != TaskStatusEnum.FAILED:
                    model.failure_reason = None

                # Update the model's updated_at field if it exists
                if hasattr(model, 'updated_at'):
                    model.updated_at = datetime.utcnow()

                await self.session.commit()
                await self.session.refresh(model)
                return True
            return False
        except Exception as e:
            # Rollback on error to prevent transaction abortion
            await self.session.rollback()
            raise e

    async def count_by_status(self, status: TaskStatus) -> int:
        """Count tasks by status."""
        stmt = (
            select(func.count())
            .select_from(TaskModel)
            .where(TaskModel.status == TaskStatusEnum(status.value))
        )
        result = await self.session.execute(stmt)
        return result.scalar()

    async def get_queue_stats(self) -> dict:
        """Get queue statistics."""
        stats = {}
        for status in TaskStatus:
            count = await self.count_by_status(status)
            stats[status.value] = count
        return stats

    async def count_high_priority_tasks(
        self, status: TaskStatus, priority_threshold: int = 7
    ) -> int:
        """Count tasks at or above a given priority for a specific status."""
        stmt = (
            select(func.count())
            .select_from(TaskModel)
            .where(
                TaskModel.status == TaskStatusEnum(status.value),
                TaskModel.priority >= priority_threshold,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def get_recent_failures(self, hours: int = 24) -> List[ParsingTask]:
        """Return failed tasks within the past N hours."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        stmt = (
            select(TaskModel)
            .where(
                TaskModel.status == TaskStatusEnum.FAILED,
                TaskModel.updated_at >= cutoff,
            )
            .order_by(TaskModel.updated_at.desc())
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return [self._to_domain(model) for model in models]

    async def get_completed_tasks_with_timing(self, limit: int = 100) -> List[ParsingTask]:
        """Return recently completed tasks with timing metadata."""
        stmt = (
            select(TaskModel)
            .where(TaskModel.status == TaskStatusEnum.COMPLETED)
            .order_by(TaskModel.completed_at.desc().nullslast())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return [self._to_domain(model) for model in models]

    async def cleanup_old_completed_tasks(self, days_to_retain: int = 90) -> int:
        """Delete completed tasks older than the retention window."""
        cutoff = datetime.utcnow() - timedelta(days=days_to_retain)
        stmt = (
            delete(TaskModel)
            .where(
                TaskModel.status == TaskStatusEnum.COMPLETED,
                TaskModel.completed_at.isnot(None),
                TaskModel.completed_at < cutoff,
            )
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount or 0
