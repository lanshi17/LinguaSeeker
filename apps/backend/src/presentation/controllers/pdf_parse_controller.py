from fastapi import (
    APIRouter,
    HTTPException,
    BackgroundTasks,
    UploadFile,
    File,
    Form,
    Query,
)
from fastapi.responses import JSONResponse
from typing import Optional, Union
from pydantic import BaseModel
import uuid
import base64
from datetime import datetime
import secrets

from src.presentation.base_controller import BaseController
from src.presentation.dtos.request.pdf_upload_request import PDFUploadRequest, UploadSource
from src.presentation.dtos.response.task_status_response import TaskStatusResponse
from src.application.services.pdf_parse_service import PDFParseService
from src.domain.models.parsing_task import (
    ParsingTask,
    TaskStatus as DomainTaskStatus,
    TaskType as DomainTaskType,
)
from src.domain.models.document import Document
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
            summary="Upload PDF document for parsing (JSON with Base64)",
        )(self.upload_pdf)

        self.router.post(
            "/pdf/upload/form",
            response_model=dict,
            tags=["PDF Parsing"],
            summary="Upload PDF document for parsing (multipart/form-data)",
        )(self.upload_pdf_form)

        self.router.post(
            "/pdf/fetch-by-pmid",
            response_model=dict,
            tags=["PDF Parsing"],
            summary="Fetch and parse document by PMID",
        )(self.fetch_by_pmid)

        self.router.post(
            "/pdf/fetch-by-doi",
            response_model=dict,
            tags=["PDF Parsing"],
            summary="Fetch and parse document by DOI",
        )(self.fetch_by_doi)

        # Status endpoints
        self.router.get(
            "/tasks/{task_id}",
            response_model=TaskStatusResponse,
            tags=["Task Management"],
            summary="Get parsing task status",
        )(self.get_task_status)

        self.router.get(
            "/tasks/{task_id}/progress",
            response_model=dict,
            tags=["Task Management"],
            summary="Get real-time task progress",
        )(self.get_task_progress)

        # Management endpoints
        self.router.post(
            "/tasks/{task_id}/retry",
            response_model=dict,
            tags=["Task Management"],
            summary="Retry failed parsing task",
        )(self.retry_task)

        self.router.delete(
            "/tasks/{task_id}",
            response_model=dict,
            tags=["Task Management"],
            summary="Cancel parsing task",
        )(self.cancel_task)

    async def upload_pdf(
        self,
        request: PDFUploadRequest,
        background_tasks: BackgroundTasks,
        use_existing: bool = Query(False),
        force: bool = Query(False),
    ):
        """
        Upload a PDF document for asynchronous parsing.

        Creates a new parsing task and returns the task ID immediately.
        The actual parsing happens asynchronously in the background.
        """
        try:
            source = self._resolve_source(request.source)
            filename_info = request.filename if request.filename else "PMID/DOI fetch"
            self.logger.info(f"Received PDF upload request: {filename_info}")

            duplicate_document = None
            file_bytes = None
            if source == UploadSource.FILE:
                file_bytes = self._validate_file_upload_request(request)
                duplicate_document = await self.pdf_parse_service.find_duplicate_document(
                    request, file_bytes, request.filename
                )
            elif source in (UploadSource.PMID, UploadSource.DOI):
                self._validate_identifier_request(request, source)
            else:
                raise HTTPException(status_code=400, detail="Unsupported upload source")

            if duplicate_document and not force:
                return self._handle_duplicate_document(
                    duplicate_document, request, use_existing
                )

            document_id = (
                duplicate_document.id if duplicate_document else uuid.uuid4()
            )
            task_id = uuid.uuid4()
            current_time = datetime.utcnow()

            # Ensure placeholder document exists to satisfy FK constraints
            if not duplicate_document:
                await self._ensure_document_placeholder(document_id, request)

            task_type = (
                DomainTaskType.IDENTIFIER_RESOLVE
                if source in (UploadSource.PMID, UploadSource.DOI)
                else DomainTaskType.PDF_PARSE
            )

            parsing_task = ParsingTask(
                id=task_id,
                document_id=document_id,
                status=DomainTaskStatus.PENDING,
                task_type=task_type,
                priority=request.priority or 0,
                created_at=current_time,
                updated_at=current_time,
            )

            parsing_task = await self.pdf_parse_service.save_parsing_task(parsing_task)

            # Start background processing
            background_tasks.add_task(
                self.pdf_parse_service.process_document_async,
                parsing_task=parsing_task,
                upload_request=request,
            )

            self.logger.info(
                f"Created parsing task {parsing_task.id} for document {parsing_task.document_id}"
            )

            response_body = {
                "task_id": str(parsing_task.id),
                "document_id": str(parsing_task.document_id),
                "status": "pending",
                "message": "Document upload accepted. Processing started in background.",
                "websocket_url": f"/ws/task/{parsing_task.id}/progress",
                "server_hash": getattr(request, "content_hash", None),
                "client_hash": request.client_hash,
                "match": (
                    request.client_hash == getattr(request, "content_hash", None)
                    if request.client_hash
                    else None
                ),
            }
            status_code = 201 if not duplicate_document else 200
            return JSONResponse(status_code=status_code, content=response_body)

        except HTTPException:
            raise
        except Exception as e:
            self.logger.error(f"Error creating PDF parsing task: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Internal server error: {str(e)}"
            )

    async def upload_pdf_form(
        self,
        file: UploadFile = File(..., description="PDF file to upload"),
        priority: int = Form(0, description="Processing priority (0-10)", ge=0, le=10),
        background_tasks: BackgroundTasks = None,
        use_existing: bool = Query(False),
        force: bool = Query(False),
        client_hash: Optional[str] = Form(None),
    ):
        """
        Upload a PDF document using multipart/form-data for parsing.

        This endpoint accepts direct file uploads via form-data.
        Creates a new parsing task and returns the task ID immediately.
        The actual parsing happens asynchronously in the background.
        """
        try:
            self.logger.info(f"Received PDF form upload: {file.filename}")

            # Validate file
            if not file.filename:
                raise HTTPException(status_code=400, detail="Filename is required")

            # Read file content
            file_content = await file.read()

            # Validate file size
            if len(file_content) > self.config.max_upload_size:
                raise HTTPException(
                    status_code=400,
                    detail=f"File size exceeds maximum limit of {self.config.max_upload_size} bytes",
                )

            # Check if it looks like a PDF
            if len(file_content) > 4 and file_content[:4] != b"%PDF":
                raise HTTPException(
                    status_code=400, detail="File does not appear to be a valid PDF"
                )

            # Convert to base64
            base64_content = base64.b64encode(file_content).decode("utf-8")

            # Create request object
            request = PDFUploadRequest(
                file_content=base64_content,
                filename=file.filename,
                source=UploadSource.FILE,
                priority=priority,
                client_hash=client_hash,
            )

            # Use the existing upload logic with new BackgroundTasks
            background_tasks = background_tasks or BackgroundTasks()
            return await self.upload_pdf(
                request, background_tasks, use_existing, force
            )

        except HTTPException:
            raise
        except Exception as e:
            self.logger.error(f"Error creating PDF parsing task from form: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Internal server error: {str(e)}"
            )

    async def fetch_by_pmid(
        self,
        pmid: str,
        priority: Optional[int] = 0,
        background_tasks: BackgroundTasks = None,
        use_existing: bool = Query(False),
        force: bool = Query(False),
    ):
        """
        Fetch document by PMID and create parsing task.
        """
        request = PDFUploadRequest(pmid=pmid, source=UploadSource.PMID, priority=priority)
        # Reuse the upload logic
        from fastapi.background import BackgroundTasks

        background_tasks = background_tasks or BackgroundTasks()
        return await self.upload_pdf(request, background_tasks, use_existing, force)

    async def fetch_by_doi(
        self,
        doi: str,
        priority: Optional[int] = 0,
        background_tasks: BackgroundTasks = None,
        use_existing: bool = Query(False),
        force: bool = Query(False),
    ):
        """
        Fetch document by DOI and create parsing task.
        """
        request = PDFUploadRequest(doi=doi, source=UploadSource.DOI, priority=priority)
        # Reuse the upload logic
        from fastapi.background import BackgroundTasks

        background_tasks = background_tasks or BackgroundTasks()
        return await self.upload_pdf(request, background_tasks, use_existing, force)

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
                raise HTTPException(
                    status_code=404, detail="Task not found or cannot be retried"
                )
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
                raise HTTPException(
                    status_code=404, detail="Task not found or cannot be cancelled"
                )
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

    async def _ensure_document_placeholder(
        self, document_id: uuid.UUID, request: PDFUploadRequest
    ) -> None:
        """Insert a placeholder document so parsing_tasks FK constraints are satisfied."""
        title_candidates = filter(
            None,
            [
                request.filename,
                f"PMID {request.pmid}" if request.pmid else None,
                f"DOI {request.doi}" if request.doi else None,
            ],
        )
        title = next(title_candidates, f"Pending Document {document_id}")

        placeholder_document = Document(
            id=document_id,
            title=title,
            content_hash=secrets.token_hex(32),
            file_size_bytes=0,
            page_count=0,
            storage_path=f"pending/{document_id}",
        )

        await self.pdf_parse_service.save_document(placeholder_document)

    def _resolve_source(self, source: Optional[Union[str, UploadSource]]) -> UploadSource:
        """Normalize the upload source value to an UploadSource enum."""
        if isinstance(source, UploadSource):
            return source
        if isinstance(source, str):
            try:
                return UploadSource(source.lower())
            except ValueError:
                return UploadSource.FILE
        return UploadSource.FILE

    def _validate_file_upload_request(self, request: PDFUploadRequest) -> bytes:
        """Validate base64 payloads before accepting the upload."""
        if not request.file_content or not request.filename:
            raise HTTPException(
                status_code=400,
                detail="File content and filename are required for file uploads",
            )

        try:
            file_bytes = base64.b64decode(request.file_content, validate=True)
        except Exception:
            raise HTTPException(
                status_code=400, detail="Invalid base64 encoded file content"
            )

        if len(file_bytes) > self.config.max_upload_size:
            raise HTTPException(
                status_code=400,
                detail=f"File size exceeds maximum limit of {self.config.max_upload_size} bytes",
            )

        if len(file_bytes) < 4 or file_bytes[:4] != b"%PDF":
            raise HTTPException(
                status_code=400, detail="Uploaded file is not a valid PDF"
            )
        return file_bytes

    def _validate_identifier_request(
        self, request: PDFUploadRequest, source: UploadSource
    ) -> None:
        """Validate PMID/DOI identifiers before enqueuing work."""
        if source == UploadSource.PMID:
            identifier = request.pmid
            if not identifier:
                raise HTTPException(status_code=400, detail="PMID is required")
            if not self.pdf_parse_service.validate_pmid(identifier):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid PMID format. Must be 1-8 digits.",
                )
        elif source == UploadSource.DOI:
            identifier = request.doi
            if not identifier:
                raise HTTPException(status_code=400, detail="DOI is required")
            if not self.pdf_parse_service.validate_doi(identifier):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid DOI format.",
                )

    def _handle_duplicate_document(
        self, document: Document, request: PDFUploadRequest, use_existing: bool
    ):
        """Handle duplicate document behavior with configurable reuse."""
        self.logger.warning(
            f"Duplicate document detected: hash={document.content_hash}, existing_id={document.id}"
        )
        server_hash = getattr(request, "content_hash", None)
        client_hash = request.client_hash
        match = (
            client_hash == server_hash if client_hash and server_hash else None
        )

        if use_existing:
            payload = {
                "document_id": str(document.id),
                "status": document.processing_status.value.lower()
                if hasattr(document.processing_status, "value")
                else str(document.processing_status).lower(),
                "message": "使用已有文档",
                "detail": "Existing document reused.",
                "server_hash": server_hash,
                "client_hash": client_hash,
                "match": match,
            }
            return JSONResponse(status_code=200, content=payload)

        payload = {
            "error": "DUPLICATE_DOCUMENT",
            "message": "Document with hash already exists",
            "existing_document_id": str(document.id),
            "server_hash": server_hash,
            "client_hash": client_hash,
            "match": match,
        }
        headers = {"X-Existing-Document-Id": str(document.id)}
        return JSONResponse(status_code=409, content=payload, headers=headers)
