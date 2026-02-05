from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
import hashlib
from contextlib import asynccontextmanager

from src.application.services.base_service import BaseService
from src.domain.models.parsing_task import ParsingTask, TaskStatus, TaskStage, TaskType
from src.domain.models.document import Document
from src.infrastructure.repositories.postgres.task_repository_impl import TaskRepositoryImpl
from src.infrastructure.repositories.postgres.document_repository_impl import DocumentRepositoryImpl
from src.utils.logger import Logger
from src.config.app_config import AppConfig
from src.infrastructure.database.session_factory import db_session_factory


class TaskManagementService(BaseService):
    """
    Service for managing parsing tasks including creation, status tracking, and lifecycle management.

    This service provides comprehensive task management functionality:
    - Create and initialize new parsing tasks
    - Query task status and progress
    - Handle task prioritization
    - Manage retry logic for failed tasks
    - Provide queue monitoring and statistics
    """

    def __init__(self, config: AppConfig = None):
        super().__init__(config or AppConfig.from_env())
        self.logger = Logger()

    @asynccontextmanager
    async def _task_repo(self):
        async with db_session_factory.get_session_context() as session:
            yield TaskRepositoryImpl(session)

    @asynccontextmanager
    async def _document_repo(self):
        async with db_session_factory.get_session_context() as session:
            yield DocumentRepositoryImpl(session)

    async def create_task(
        self,
        document_id: str = None,
        priority: int = 5,
        source_type: str = "file"
    ) -> ParsingTask:
        """
        Create a new parsing task.

        Args:
            document_id: Optional document ID to associate with the task
            priority: Task priority (0-10, where 10 is highest)
            source_type: Source type ("file", "pmid", "doi")

        Returns:
            Created parsing task
        """
        self.logger.info(f"Creating new parsing task with priority {priority}")

        # Generate document ID if not provided
        if document_id:
            document_uuid = uuid.UUID(str(document_id))
        else:
            document_uuid = uuid.uuid4()
            document_id = str(document_uuid)

        # Create parsing task
        normalized_source = (source_type or "file").lower()
        task_type = (
            TaskType.IDENTIFIER_RESOLVE
            if normalized_source in ("pmid", "doi")
            else TaskType.PDF_PARSE
        )

        # Ensure corresponding document placeholder exists before creating the task
        await self._ensure_document_placeholder(document_uuid, normalized_source)

        task = ParsingTask(
            id=uuid.uuid4(),
            document_id=document_uuid,
            task_type=task_type,
            priority=priority,
            created_at=datetime.utcnow()
        )

        # Save to repository
        async with self._task_repo() as task_repo:
            await task_repo.save(task)

        # Audit logging currently reduced to structured logs
        self.logger.info(
            f"Task created: task_id={task.id} document_id={document_id} "
            f"priority={priority} source_type={source_type}"
        )

        self.logger.info(f"Created parsing task {task.id} for document {document_id}")
        return task

    async def _ensure_document_placeholder(self, document_id: uuid.UUID, source_type: str) -> None:
        """Create a placeholder document so FK constraints are satisfied."""
        async with self._document_repo() as doc_repo:
            existing = await doc_repo.find_by_id(document_id)
            if existing:
                return

            content_hash = hashlib.sha256(f"placeholder:{document_id}".encode("utf-8")).hexdigest()
            placeholder = Document(
                id=document_id,
                title=f"Pending Document {document_id}",
                content_hash=content_hash,
                file_size_bytes=0,
                page_count=0,
                storage_path=f"pending/{document_id}",
                metadata={"source": source_type},
            )
            await doc_repo.save(placeholder)

    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the current status of a parsing task.

        Args:
            task_id: Task identifier

        Returns:
            Task status information or None if not found
        """
        try:
            async with self._task_repo() as task_repo:
                task = await task_repo.get_by_id(task_id)
            if not task:
                return None

            return {
                "task_id": str(task.id),
                "document_id": str(task.document_id),
                "status": task.status.value.lower(),
                "progress_percentage": task.progress_percentage,
                "current_stage": task.current_stage.value.lower(),
                "priority": task.priority,
                "retry_count": task.retry_count,
                "failure_reason": task.failure_reason,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "estimated_completion": task.estimated_completion.isoformat() if task.estimated_completion else None
            }
        except Exception as e:
            self.logger.error(f"Error getting task status for {task_id}: {str(e)}")
            raise

    async def get_task_progress(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get real-time progress information for a parsing task.

        Args:
            task_id: Task identifier

        Returns:
            Task progress information or None if not found
        """
        try:
            async with self._task_repo() as task_repo:
                task = await task_repo.get_by_id(task_id)
            if not task:
                return None

            return {
                "task_id": str(task.id),
                "status": task.status.value.lower(),
                "progress_percentage": task.progress_percentage,
                "current_stage": task.current_stage.value.lower(),
                "updated_at": task.updated_at.isoformat() if task.updated_at else None
            }
        except Exception as e:
            self.logger.error(f"Error getting task progress for {task_id}: {str(e)}")
            raise

    async def set_task_priority(self, task_id: str, priority: int) -> bool:
        """
        Set the priority of a parsing task.

        Args:
            task_id: Task identifier
            priority: New priority (0-10)

        Returns:
            True if successful, False if task not found or invalid priority
        """
        if not (0 <= priority <= 10):
            self.logger.warning(f"Invalid priority {priority} for task {task_id}")
            return False

        try:
            async with self._task_repo() as task_repo:
                task = await task_repo.get_by_id(task_id)
                if not task:
                    return False

                old_priority = task.priority
                task.priority = priority
                await task_repo.save(task)

            self.logger.info(
                f"Task priority updated: task_id={task_id} old={old_priority} new={priority}"
            )

            self.logger.info(f"Set priority {priority} for task {task_id}")
            return True

        except Exception as e:
            self.logger.error(f"Error setting priority for task {task_id}: {str(e)}")
            return False

    async def retry_task(self, task_id: str) -> bool:
        """
        Retry a failed parsing task.

        Args:
            task_id: Task identifier

        Returns:
            True if successful, False if task cannot be retried
        """
        try:
            async with self._task_repo() as task_repo:
                task = await task_repo.get_by_id(task_id)
                if not task:
                    return False

                if not task.can_retry():
                    self.logger.warning(f"Cannot retry task {task_id} in status {task.status}")
                    return False

                task.retry()
                await task_repo.save(task)

            self.logger.info(f"Retried task {task_id} (attempt {task.retry_count})")
            return True

        except Exception as e:
            self.logger.error(f"Error retrying task {task_id}: {str(e)}")
            return False

    async def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a pending or processing parsing task.

        Args:
            task_id: Task identifier

        Returns:
            True if successful, False if task cannot be cancelled
        """
        try:
            async with self._task_repo() as task_repo:
                task = await task_repo.get_by_id(task_id)
                if not task:
                    return False

                if task.is_terminal():
                    self.logger.warning(f"Cannot cancel task {task_id} in terminal status {task.status}")
                    return False

                task.fail("Task cancelled by user")
                await task_repo.save(task)

            self.logger.info(f"Cancelled task {task_id}")
            return True

        except Exception as e:
            self.logger.error(f"Error cancelling task {task_id}: {str(e)}")
            return False

    async def get_queue_status(self) -> Dict[str, Any]:
        """
        Get the current status of all task queues.

        Returns:
            Queue statistics including counts by status and priority
        """
        try:
            async with self._task_repo() as task_repo:
                pending_count = await task_repo.count_by_status(TaskStatus.PENDING)
                processing_count = await task_repo.count_by_status(TaskStatus.PROCESSING)
                completed_count = await task_repo.count_by_status(TaskStatus.COMPLETED)
                failed_count = await task_repo.count_by_status(TaskStatus.FAILED)
                retry_count = await task_repo.count_by_status(TaskStatus.RETRY)

                high_priority_pending = await task_repo.count_high_priority_tasks(
                    TaskStatus.PENDING, priority_threshold=7
                )
                high_priority_processing = await task_repo.count_high_priority_tasks(
                    TaskStatus.PROCESSING, priority_threshold=7
                )

                recent_failures = await task_repo.get_recent_failures(hours=24)

            return {
                "total_tasks": pending_count + processing_count + completed_count + failed_count + retry_count,
                "pending_tasks": pending_count,
                "processing_tasks": processing_count,
                "completed_tasks": completed_count,
                "failed_tasks": failed_count,
                "retry_tasks": retry_count,
                "high_priority_pending": high_priority_pending,
                "high_priority_processing": high_priority_processing,
                "recent_failures_24h": len(recent_failures),
                "failure_rate": (
                    failed_count / (completed_count + failed_count) * 100
                    if (completed_count + failed_count) > 0 else 0
                ),
                "average_processing_time_seconds": await self._get_average_processing_time()
            }

        except Exception as e:
            self.logger.error(f"Error getting queue status: {str(e)}")
            raise

    async def _get_average_processing_time(self) -> float:
        """
        Calculate average processing time for completed tasks.
        """
        try:
            async with self._task_repo() as task_repo:
                completed_tasks = await task_repo.get_completed_tasks_with_timing(limit=100)
            if not completed_tasks:
                return 0.0

            total_time = 0.0
            count = 0
            for task in completed_tasks:
                if task.started_at and task.completed_at:
                    elapsed = (task.completed_at - task.started_at).total_seconds()
                    total_time += elapsed
                    count += 1

            return total_time / count if count > 0 else 0.0
        except Exception:
            return 0.0

    async def get_tasks_by_status(
        self,
        status: str,
        limit: int = 50,
        offset: int = 0,
        priority_filter: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get tasks filtered by status.

        Args:
            status: Task status filter
            limit: Maximum number of results
            offset: Pagination offset
            priority_filter: Optional priority filter

        Returns:
            List of task information
        """
        try:
            async with self._task_repo() as task_repo:
                tasks = await task_repo.find_by_status(
                    status, limit=limit, offset=offset, priority_filter=priority_filter
                )

            return [
                {
                    "task_id": str(task.id),
                    "document_id": str(task.document_id),
                    "status": task.status.value.lower(),
                    "progress_percentage": task.progress_percentage,
                    "current_stage": task.current_stage.value.lower(),
                    "priority": task.priority,
                    "created_at": task.created_at.isoformat() if task.created_at else None,
                    "updated_at": task.updated_at.isoformat() if task.updated_at else None
                }
                for task in tasks
            ]

        except Exception as e:
            self.logger.error(f"Error getting tasks by status {status}: {str(e)}")
            raise

    async def cleanup_completed_tasks(self, days_to_retain: int = 90) -> int:
        """
        Clean up completed tasks older than the retention period.

        Args:
            days_to_retain: Number of days to retain completed tasks

        Returns:
            Number of tasks deleted
        """
        try:
            async with self._task_repo() as task_repo:
                deleted_count = await task_repo.cleanup_old_completed_tasks(days_to_retain)
            self.logger.info(f"Cleaned up {deleted_count} completed tasks older than {days_to_retain} days")
            return deleted_count
        except Exception as e:
            self.logger.error(f"Error cleaning up completed tasks: {str(e)}")
            raise

    def perform_service(self, *args, **kwargs):
        """Abstract method implementation - not used in this service."""
        pass
