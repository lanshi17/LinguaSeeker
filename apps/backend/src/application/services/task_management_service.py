import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

from src.application.services.base_service import BaseService
from src.domain.models.parsing_task import ParsingTask, TaskStatus, TaskStage
from src.infrastructure.repositories.postgres.task_repository_impl import TaskRepositoryImpl
from src.infrastructure.repositories.postgres.document_repository_impl import DocumentRepositoryImpl
from src.infrastructure.repositories.postgres.audit_log_repository_impl import AuditLogRepositoryImpl
from src.utils.logger import Logger
from src.config.app_config import AppConfig


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
        from src.infrastructure.database.session_factory import get_db_session
        self.task_repository = TaskRepositoryImpl(get_db_session())
        self.document_repository = DocumentRepositoryImpl(get_db_session())
        self.audit_log_repository = AuditLogRepositoryImpl(get_db_session())

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
        if not document_id:
            document_id = str(uuid.uuid4())

        # Create parsing task
        task = ParsingTask(
            id=uuid.uuid4(),
            document_id=uuid.UUID(document_id),
            priority=priority,
            created_at=datetime.utcnow()
        )

        # Save to repository
        await self.task_repository.save(task)

        # Log task creation
        await self.audit_log_repository.log_task_creation(
            task_id=str(task.id),
            document_id=document_id,
            priority=priority,
            source_type=source_type
        )

        self.logger.info(f"Created parsing task {task.id} for document {document_id}")
        return task

    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the current status of a parsing task.

        Args:
            task_id: Task identifier

        Returns:
            Task status information or None if not found
        """
        try:
            task = await self.task_repository.get_by_id(task_id)
            if not task:
                return None

            return {
                "task_id": str(task.id),
                "document_id": str(task.document_id),
                "status": task.status.value,
                "progress_percentage": task.progress_percentage,
                "current_stage": task.current_stage.value,
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
            task = await self.task_repository.get_by_id(task_id)
            if not task:
                return None

            return {
                "task_id": str(task.id),
                "status": task.status.value,
                "progress_percentage": task.progress_percentage,
                "current_stage": task.current_stage.value,
                "updated_at": task.created_at.isoformat() if task.created_at else None
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
            task = await self.task_repository.get_by_id(task_id)
            if not task:
                return False

            # Update priority
            task.priority = priority
            await self.task_repository.save(task)

            # Log priority change
            await self.audit_log_repository.log_task_priority_change(
                task_id=task_id,
                old_priority=task.priority,
                new_priority=priority
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
            task = await self.task_repository.get_by_id(task_id)
            if not task:
                return False

            if not task.can_retry():
                self.logger.warning(f"Cannot retry task {task_id} in status {task.status}")
                return False

            # Retry the task
            task.retry()
            await self.task_repository.save(task)

            # Log retry
            await self.audit_log_repository.log_task_retry(
                task_id=task_id,
                retry_count=task.retry_count
            )

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
            task = await self.task_repository.get_by_id(task_id)
            if not task:
                return False

            if task.is_terminal():
                self.logger.warning(f"Cannot cancel task {task_id} in terminal status {task.status}")
                return False

            # Mark as failed with cancellation reason
            task.fail("Task cancelled by user")
            await self.task_repository.save(task)

            # Log cancellation
            await self.audit_log_repository.log_task_cancellation(task_id)

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
            # Get counts by status
            pending_count = await self.task_repository.count_by_status(TaskStatus.PENDING)
            processing_count = await self.task_repository.count_by_status(TaskStatus.PROCESSING)
            completed_count = await self.task_repository.count_by_status(TaskStatus.COMPLETED)
            failed_count = await self.task_repository.count_by_status(TaskStatus.FAILED)
            retry_count = await self.task_repository.count_by_status(TaskStatus.RETRY)

            # Get high priority tasks
            high_priority_pending = await self.task_repository.count_high_priority_tasks(
                TaskStatus.PENDING, priority_threshold=7
            )
            high_priority_processing = await self.task_repository.count_high_priority_tasks(
                TaskStatus.PROCESSING, priority_threshold=7
            )

            # Get recent failures
            recent_failures = await self.task_repository.get_recent_failures(hours=24)

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
            completed_tasks = await self.task_repository.get_completed_tasks_with_timing(limit=100)
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
            tasks = await self.task_repository.find_by_status(
                status, limit=limit, offset=offset, priority_filter=priority_filter
            )

            return [
                {
                    "task_id": str(task.id),
                    "document_id": str(task.document_id),
                    "status": task.status.value,
                    "progress_percentage": task.progress_percentage,
                    "current_stage": task.current_stage.value,
                    "priority": task.priority,
                    "created_at": task.created_at.isoformat() if task.created_at else None,
                    "updated_at": task.created_at.isoformat() if task.created_at else None
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
            deleted_count = await self.task_repository.cleanup_old_completed_tasks(days_to_retain)
            self.logger.info(f"Cleaned up {deleted_count} completed tasks older than {days_to_retain} days")
            return deleted_count
        except Exception as e:
            self.logger.error(f"Error cleaning up completed tasks: {str(e)}")
            raise

    def perform_service(self, *args, **kwargs):
        """Abstract method implementation - not used in this service."""
        pass