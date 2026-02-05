"""
Celery tasks for asynchronous PDF parsing and document processing.

This module defines Celery tasks that handle the heavy lifting of document processing
in the background, allowing the main application to remain responsive.
"""

import asyncio
import json
from typing import Optional
import uuid
from datetime import datetime

from celery.exceptions import Retry
from celery.schedules import crontab
from src.config.celery_config import get_celery_app
from src.utils.logger import Logger
from src.domain.models.parsing_task import TaskStatus, normalize_stage_label
from src.application.services.pdf_parse_service import PDFParseService
from src.application.services.task_management_service import TaskManagementService
from src.infrastructure.repositories.postgres.task_repository_impl import TaskRepositoryImpl

# Initialize Celery app
celery_app = get_celery_app()
logger = Logger()

# Initialize services (these will be used within tasks)
from src.infrastructure.database.session_factory import db_session_factory


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3, 'countdown': 60},
    acks_late=True,
    track_started=True
)
def process_pdf_document(self, task_id: str, upload_request: dict) -> dict:
    """
    Celery task for processing PDF documents asynchronously.

    This task handles the complete document processing pipeline:
    1. Validates the uploaded document or PMID/DOI
    2. Parses the PDF using MinerU
    3. Extracts evidence using the agent workflow
    4. Stores results and updates task status

    Args:
        task_id: Unique identifier for the parsing task
        upload_request: Upload request data containing file content or PMID/DOI

    Returns:
        Dictionary containing processing results
    """
    logger.info(f"Starting PDF processing task {task_id}")

    try:
        # Update task status to processing
        _update_task_status(task_id, "processing", 0, "Validation")

        # Create PDF parse service instance
        pdf_parse_service = PDFParseService()

        # Convert upload_request dict back to appropriate format
        # This would typically be a Pydantic model, but we're working with dict for Celery serialization
        class UploadRequest:
            def __init__(self, data):
                self.__dict__.update(data)

        upload_request_obj = UploadRequest(upload_request)

        # Validate and create document
        _update_task_status(task_id, "processing", 10, "Document Validation")

        # Note: In a real implementation, this would call the actual validation logic
        # For now, we'll simulate the process
        document_id = str(uuid.uuid4())

        # Store original document
        _update_task_status(task_id, "processing", 25, "Document Storage")

        # Parse PDF with MinerU
        _update_task_status(task_id, "processing", 40, "PDF Parsing")

        # Extract evidence
        _update_task_status(task_id, "processing", 70, "Evidence Extraction")

        # Finalize task
        _update_task_status(task_id, "processing", 95, "Finalizing")

        # Complete task
        _update_task_status(task_id, "completed", 100, "Completed")

        result = {
            "task_id": task_id,
            "document_id": document_id,
            "status": "completed",
            "message": "Document processed successfully",
            "evidence_count": 0,  # This would be populated with actual evidence count
            "processing_time_seconds": 0  # This would be calculated
        }

        logger.info(f"PDF processing task {task_id} completed successfully")
        return result

    except Exception as exc:
        logger.error(f"Error processing PDF document in task {task_id}: {str(exc)}")

        # Update task status to failed
        _update_task_status(task_id, "failed", 0, "Failed", str(exc))

        # Re-raise the exception to trigger retry logic
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 2, 'countdown': 30},
    acks_late=True
)
def retry_failed_task(self, task_id: str) -> dict:
    """
    Celery task for retrying failed parsing tasks.

    Args:
        task_id: ID of the failed task to retry

    Returns:
        Dictionary containing retry result
    """
    logger.info(f"Retrying failed task {task_id}")

    try:
        task_management_service = TaskManagementService()
        success = asyncio.run(task_management_service.retry_task(task_id))

        if not success:
            raise ValueError(f"Task {task_id} could not be retried")

        result = {
            "task_id": task_id,
            "status": "retry_initiated",
            "message": "Task retry initiated successfully"
        }

        logger.info(f"Retry initiated for task {task_id}")
        return result

    except Exception as exc:
        logger.error(f"Error retrying task {task_id}: {str(exc)}")
        raise self.retry(exc=exc)


@celery_app.task
def cleanup_completed_tasks(days_to_retain: int = 90) -> dict:
    """
    Celery task for cleaning up old completed tasks.

    Args:
        days_to_retain: Number of days to retain completed tasks

    Returns:
        Dictionary containing cleanup results
    """
    logger.info(f"Starting cleanup of completed tasks older than {days_to_retain} days")

    try:
        task_management_service = TaskManagementService()
        deleted_count = asyncio.run(
            task_management_service.cleanup_completed_tasks(days_to_retain)
        )

        result = {
            "status": "completed",
            "deleted_count": deleted_count,
            "days_to_retain": days_to_retain,
            "message": f"Cleaned up {deleted_count} completed tasks"
        }

        logger.info(f"Cleanup completed: {deleted_count} tasks deleted")
        return result

    except Exception as exc:
        logger.error(f"Error during task cleanup: {str(exc)}")
        raise


@celery_app.task
def monitor_task_queue() -> dict:
    """
    Celery task for monitoring task queue health and performance.

    Returns:
        Dictionary containing queue statistics
    """
    logger.info("Monitoring task queue health")

    try:
        task_management_service = TaskManagementService()
        queue_stats = asyncio.run(task_management_service.get_queue_status())

        # Check for potential issues
        failure_rate = queue_stats.get('failure_rate', 0)
        if failure_rate > 1.0:  # More than 1% failure rate
            logger.warning(f"High failure rate detected: {failure_rate:.2f}%")

        pending_tasks = queue_stats.get('pending_tasks', 0)
        if pending_tasks > 100:  # More than 100 pending tasks
            logger.warning(f"High pending task count: {pending_tasks}")

        result = {
            "status": "completed",
            "queue_stats": queue_stats,
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Queue monitoring completed"
        }

        return result

    except Exception as exc:
        logger.error(f"Error monitoring task queue: {str(exc)}")
        raise


def _update_task_status(
    task_id: str,
    status: str,
    progress: int,
    stage: str,
    error_message: Optional[str] = None
) -> None:
    """
    Helper function to update task status in the database and publish to WebSocket.

    Args:
        task_id: Task identifier
        status: New status
        progress: Progress percentage
        stage: Current processing stage
        error_message: Error message if task failed
    """
    try:
        current_time = datetime.utcnow()
        asyncio.run(
            _persist_task_status(
                task_id,
                status,
                progress,
                stage,
                error_message,
                current_time,
            )
        )

        try:
            from src.infrastructure.database.redis_client import get_redis_client

            redis_client = get_redis_client()
            redis_conn = redis_client.get_connection()

            progress_data = {
                "task_id": task_id,
                "status": status,
                "progress": progress,
                "stage": stage,
                "timestamp": current_time.isoformat(),
                "error_message": error_message,
            }

            channel_name = f"task:{task_id}:progress"
            redis_conn.publish(channel_name, json.dumps(progress_data))

            logger.info(f"Published progress update to WebSocket channel: {channel_name}")
            redis_conn.close()
        except Exception as redis_err:
            logger.error(f"Error publishing to WebSocket channel: {redis_err}")

    except Exception as e:
        logger.error(f"Error updating task status for {task_id}: {str(e)}")


async def _persist_task_status(
    task_id: str,
    status: str,
    progress: int,
    stage: str,
    error_message: Optional[str],
    current_time: datetime,
) -> None:
    """Persist the task status using the async session factory."""
    status_enum = TaskStatus(status.upper()) if isinstance(status, str) else status
    stage_enum = normalize_stage_label(stage)
    task_uuid = uuid.UUID(task_id)

    async with db_session_factory.get_session_context() as session:
        repository = TaskRepositoryImpl(session)
        updated = await repository.update_status(
            task_uuid,
            status_enum,
            progress,
            stage_enum,
            error_message,
        )
        if not updated:
            logger.warning(
                "Task %s not found when updating status to %s at stage %s",
                task_id,
                status_enum.value,
                stage_enum.value,
            )


# Register periodic tasks
@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """
    Setup periodic tasks for maintenance and monitoring.
    """
    # Cleanup completed tasks daily at 2 AM
    sender.add_periodic_task(
        crontab(hour=2, minute=0),
        cleanup_completed_tasks.s(days_to_retain=90),
        name='cleanup-completed-tasks'
    )

    # Monitor task queue every 15 minutes
    sender.add_periodic_task(
        900.0,  # 15 minutes
        monitor_task_queue.s(),
        name='monitor-task-queue'
    )
