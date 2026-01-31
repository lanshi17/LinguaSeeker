from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from typing import Optional, Union
from pydantic import BaseModel
import uuid
from datetime import datetime

from src.presentation.base_controller import BaseController
from src.presentation.dtos.request.pdf_upload_request import PDFUploadRequest
from src.presentation.dtos.response.task_status_response import TaskStatusResponse, TaskStatus
from src.application.services.pdf_parse_service import PDFParseService
from src.domain.models.parsing_task import ParsingTask
from src.utils.logger import Logger
from src.config.app_config import AppConfig


class PDFParseController(BaseController):
    """
    Controller for PDF parsing operations including upload, status checking, and progress tracking.

    This controller handles:
    - PDF file uploads (base64 encoded or PMID/DOI)
    - Asynchronous task creation and management
    - Task status queries
    - Progress tracking via WebSocket
    """

    def __init__(self, config: AppConfig = None):
        super().__init__(config or AppConfig.from_env())
        self.pdf_parse_service = PDFParseService()
        self.logger = Logger()
        self._register_routes()

    def _register_routes(self):
        """Register all PDF parsing related routes."""
        # Upload endpoints
        self.router.post(
            "/pdf/upload",
            response_model=dict,
            tags=["PDF Parsing"],
            summary="Upload PDF document for parsing"
        )(self.upload_pdf)

        self.router.post(
            "/pdf/fetch-by-pmid",
            response_model=dict,
            tags=["PDF Parsing"],
            summary="Fetch and parse document by PMID"
        )(self.fetch_by_pmid)

        self.router.post(
            "/pdf/fetch-by-doi",
            response_model=dict,
            tags=["PDF Parsing"],
            summary="Fetch and parse document by DOI"
        )(self.fetch_by_doi)

        # Status endpoints
        self.router.get(
            "/tasks/{task_id}",
            response_model=TaskStatusResponse,
            tags=["Task Management"],
            summary="Get parsing task status"
        )(self.get_task_status)

        self.router.get(
            "/tasks/{task_id}/progress",
            response_model=dict,
            tags=["Task Management"],
            summary="Get real-time task progress"
        )(self.get_task_progress)

        # Management endpoints
        self.router.post(
            "/tasks/{task_id}/retry",
            response_model=dict,
            tags=["Task Management"],
            summary="Retry failed parsing task"
        )(self.retry_task)

        self.router.delete(
            "/tasks/{task_id}",
            response_model=dict,
            tags=["Task Management"],
            summary="Cancel parsing task"
        )(self.cancel_task)

    async def upload_pdf(self, request: PDFUploadRequest, background_tasks: BackgroundTasks):
        """
        Upload a PDF document for asynchronous parsing.

        Creates a new parsing task and returns the task ID immediately.
        The actual parsing happens asynchronously in the background.
        """
        try:
            filename_info = request.filename if request.filename else 'PMID/DOI fetch'
            self.logger.info(f"Received PDF upload request: {filename_info}")

            # Validate request
            if request.source == "file":
                if not request.file_content or not request.filename:
                    raise HTTPException(
                        status_code=400,
                        detail="File content and filename are required for file uploads"
                    )
                if len(request.file_content) > self.config.max_upload_size:
                    raise HTTPException(
                        status_code=400,
                        detail=f"File size exceeds maximum limit of {self.config.max_upload_size} bytes"
                    )

            # Create parsing task
            task_id = str(uuid.uuid4())
            parsing_task = ParsingTask(
                id=task_id,
                document_id=str(uuid.uuid4()),
                status=TaskStatus.PENDING,
                priority=request.priority or 0,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )

            # Start background processing
            background_tasks.add_task(
                self.pdf_parse_service.process_document_async,
                parsing_task=parsing_task,
                upload_request=request
            )

            self.logger.info(f"Created parsing task {task_id} for document {parsing_task.document_id}")

            return {
                "task_id": task_id,
                "document_id": parsing_task.document_id,
                "status": "pending",
                "message": "Document upload accepted. Processing started in background.",
                "websocket_url": f"/ws/task/{task_id}/progress"
            }

        except HTTPException:
            raise
        except Exception as e:
            self.logger.error(f"Error creating PDF parsing task: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

    async def fetch_by_pmid(self, pmid: str, priority: Optional[int] = 0):
        """
        Fetch document by PMID and create parsing task.
        """
        request = PDFUploadRequest(
            pmid=pmid,
            source="pmid",
            priority=priority
        )
        # Reuse the upload logic
        from fastapi.background import BackgroundTasks
        background_tasks = BackgroundTasks()
        return await self.upload_pdf(request, background_tasks)

    async def fetch_by_doi(self, doi: str, priority: Optional[int] = 0):
        """
        Fetch document by DOI and create parsing task.
        """
        request = PDFUploadRequest(
            doi=doi,
            source="doi",
            priority=priority
        )
        # Reuse the upload logic
        from fastapi.background import BackgroundTasks
        background_tasks = BackgroundTasks()
        return await self.upload_pdf(request, background_tasks)

    async def get_task_status(self, task_id: str) -> TaskStatusResponse:
        """
        Get the current status of a parsing task.
        """
        try:
            task_status = await self.pdf_parse_service.get_task_status(task_id)
            if not task_status:
                raise HTTPException(status_code=404, detail="Task not found")
            return task_status
        except HTTPException:
            raise
        except Exception as e:
            self.logger.error(f"Error getting task status for {task_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    async def get_task_progress(self, task_id: str) -> dict:
        """
        Get real-time progress information for a parsing task.
        This endpoint is used by WebSocket connections for live updates.
        """
        try:
            progress = await self.pdf_parse_service.get_task_progress(task_id)
            if not progress:
                raise HTTPException(status_code=404, detail="Task not found")
            return progress
        except HTTPException:
            raise
        except Exception as e:
            self.logger.error(f"Error getting task progress for {task_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    async def retry_task(self, task_id: str) -> dict:
        """
        Retry a failed parsing task.
        """
        try:
            success = await self.pdf_parse_service.retry_task(task_id)
            if not success:
                raise HTTPException(status_code=404, detail="Task not found or cannot be retried")
            return {"message": "Task retry initiated successfully", "task_id": task_id}
        except HTTPException:
            raise
        except Exception as e:
            self.logger.error(f"Error retrying task {task_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    async def cancel_task(self, task_id: str) -> dict:
        """
        Cancel a pending or processing parsing task.
        """
        try:
            success = await self.pdf_parse_service.cancel_task(task_id)
            if not success:
                raise HTTPException(status_code=404, detail="Task not found or cannot be cancelled")
            return {"message": "Task cancelled successfully", "task_id": task_id}
        except HTTPException:
            raise
        except Exception as e:
            self.logger.error(f"Error cancelling task {task_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    def get_router(self) -> APIRouter:
        """Get the FastAPI router instance."""
        return self.router

    def handle_request(self, request: BaseModel) -> BaseModel:
        """Handle incoming requests - not used in this controller as routes are registered directly."""
        # This controller uses direct route registration, so this method is not used
        return request