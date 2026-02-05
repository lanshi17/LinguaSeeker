import base64
import re
import hashlib
from typing import Optional, Union, Dict, Any, List
from datetime import datetime
import asyncio
from pathlib import Path
from uuid import UUID

from src.application.services.base_service import BaseService
from src.domain.models.parsing_task import ParsingTask
from src.domain.models.document import Document
from src.domain.value_objects.confidence_score import ConfidenceScore
from src.infrastructure.storage.minio_storage_client import MinIOStorageClient
from src.infrastructure.adapters.mineru_adapter import MinerUAdapter
from src.infrastructure.repositories.postgres.document_repository_impl import DocumentRepositoryImpl
from src.infrastructure.repositories.postgres.task_repository_impl import TaskRepositoryImpl
from src.utils.logger import Logger
from src.utils.exceptions import FileUploadError, ValidationException
from src.config.app_config import AppConfig
from src.infrastructure.database.session_factory import db_session_factory
from src.application.services.task_management_service import TaskManagementService
from src.presentation.dtos.request.pdf_upload_request import UploadSource


class PDFParseService(BaseService):
    """
    Service for handling PDF parsing operations including validation, processing, and status management.

    This service orchestrates the entire PDF parsing pipeline:
    1. Validates uploaded PDFs or PMID/DOI requests
    2. Manages document storage and retrieval
    3. Coordinates with MinerU for PDF parsing
    4. Handles task lifecycle management
    5. Provides status and progress information
    """

    def __init__(self, config: AppConfig = None):
        super().__init__(config or AppConfig.from_env())
        self.logger = Logger()
        self.storage_client = MinIOStorageClient()
        self.mineru_adapter = MinerUAdapter()
        self.task_management_service = TaskManagementService(self.config)

    async def save_document(self, document: Document) -> Document:
        """Persist a document using a short-lived session."""
        async with db_session_factory.get_session_context() as session:
            repository = DocumentRepositoryImpl(session)
            return await repository.save(document)

    async def save_parsing_task(self, parsing_task: ParsingTask) -> ParsingTask:
        """Persist a parsing task using a short-lived session."""
        async with db_session_factory.get_session_context() as session:
            repository = TaskRepositoryImpl(session)
            return await repository.save(parsing_task)

    async def find_duplicate_document(
        self,
        upload_request: Any,
        file_bytes: Optional[bytes],
        filename: Optional[str] = None,
    ) -> Optional[Document]:
        """Return existing document that matches the computed hash, if any."""
        if not file_bytes:
            return None

        content_hash = hashlib.sha256(file_bytes).hexdigest()
        setattr(upload_request, "content_hash", content_hash)
        client_hash = getattr(upload_request, "client_hash", None)

        self.logger.info(
            "[Hash Debug] Received file: %s | type=%s | length=%s | server_hash=%s | client_hash=%s | match=%s",
            filename or getattr(upload_request, "filename", "unknown"),
            type(file_bytes).__name__,
            len(file_bytes),
            content_hash,
            client_hash,
            client_hash == content_hash if client_hash else "n/a",
        )

        async with db_session_factory.get_session_context() as session:
            repository = DocumentRepositoryImpl(session)
            return await repository.find_by_content_hash(content_hash)

    async def process_document_async(self, parsing_task: ParsingTask, upload_request: Any) -> None:
        """
        Asynchronously process a document parsing task.

        This method is designed to be called as a background task and handles the entire
        parsing workflow from validation through completion.
        """
        try:
            self.logger.info(f"Starting async processing for task {parsing_task.id}")

            # Update task status to processing
            await self._update_task_status(parsing_task.id, "processing", 0, "Validation")

            # Validate the upload request
            document = await self._validate_and_create_document(upload_request, parsing_task.document_id)

            # Store the original document
            await self._store_original_document(document, parsing_task.id)

            # Update task status to parsing
            await self._update_task_status(parsing_task.id, "processing", 25, "PDF Parsing")

            # Parse the PDF using MinerU
            parsed_content = await self._parse_pdf_with_mineru(document, parsing_task.id)

            # Update task status to evidence extraction
            await self._update_task_status(parsing_task.id, "processing", 50, "Evidence Extraction")

            # Extract evidence using agent workflow (this would be implemented in data_processing_service)
            # For now, we'll simulate this step
            evidence_items = await self._extract_evidence(parsed_content, parsing_task.id)

            # Update task status to completion
            await self._update_task_status(parsing_task.id, "processing", 90, "Finalizing")

            # Store evidence items and complete the task
            await self._finalize_task(parsing_task.id, document, evidence_items)

            await self._update_task_status(parsing_task.id, "completed", 100, "Completed")

            self.logger.info(f"Task {parsing_task.id} completed successfully")

        except Exception as e:
            self.logger.error(f"Error processing task {parsing_task.id}: {str(e)}")
            await self._handle_task_failure(parsing_task.id, str(e))

    async def _validate_and_create_document(self, upload_request: Any, document_id: str) -> Document:
        """
        Validate the upload request and create a Document entity.
        """
        self.logger.info("Validating document upload request")
        source = self._resolve_source(upload_request)

        if source == UploadSource.FILE:
            # Validate file upload
            if not upload_request.file_content:
                raise ValidationException("File content is required")
            if not upload_request.filename:
                raise ValidationException("Filename is required")

            # Decode base64 content
            try:
                file_content = base64.b64decode(upload_request.file_content)
            except Exception as e:
                raise ValidationException(f"Invalid base64 encoding: {str(e)}")

            # Validate file size
            if len(file_content) > self.config.max_upload_size:
                raise ValidationException(
                    f"File size {len(file_content)} exceeds maximum limit {self.config.max_upload_size}"
                )

            # Validate file type (basic PDF header check)
            if not self._is_valid_pdf(file_content):
                raise ValidationException("Uploaded file is not a valid PDF")

            content_hash = getattr(upload_request, "content_hash", None)
            if not content_hash:
                content_hash = hashlib.sha256(file_content).hexdigest()
            storage_path = f"uploads/{document_id}.pdf"

            document = Document(
                id=document_id,
                title=upload_request.filename,
                filename=upload_request.filename,
                content=file_content,
                content_type="application/pdf",
                content_hash=content_hash,
                file_size_bytes=len(file_content),
                page_count=0,
                storage_path=storage_path,
                metadata={"source": "file"},
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )

        else:
            # Handle PMID/DOI fetch (this would be implemented separately)
            # For now, we'll create a placeholder document
            source_type = source.value if isinstance(source, UploadSource) else str(source)
            identifier_attr = "pmid" if source == UploadSource.PMID else "doi"
            identifier = getattr(upload_request, identifier_attr, None)

            if not identifier:
                raise ValidationException(f"{source_type.upper()} identifier is required")

            # Validate PMID format (8 digits)
            if source == UploadSource.PMID:
                if not self.validate_pmid(identifier):
                    raise ValidationException("Invalid PMID format. Must be 1-8 digits.")

            # Validate DOI format (basic check)
            elif source == UploadSource.DOI:
                if not self.validate_doi(identifier):
                    raise ValidationException("Invalid DOI format.")

            content_hash = hashlib.sha256(f"{source_type}:{identifier}".encode("utf-8")).hexdigest()

            document = Document(
                id=document_id,
                title=f"{source_type.upper()} {identifier}",
                filename=f"{source_type}_{identifier}.pdf",
                content=b"",
                content_type="application/pdf",
                content_hash=content_hash,
                file_size_bytes=0,
                page_count=0,
                storage_path=f"identifiers/{document_id}",
                metadata={"source": source_type, "identifier": identifier},
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )

        return document

    def _is_valid_pdf(self, content: bytes) -> bool:
        """
        Perform basic PDF validation by checking the file header.
        """
        if len(content) < 4:
            return False

        # Check for PDF header (%PDF)
        return content[:4] == b'%PDF'

    async def _store_original_document(self, document: Document, task_id: str) -> None:
        """
        Store the original document in MinIO storage.
        """
        self.logger.info(f"Storing original document {document.id} for task {task_id}")

        # Create storage key
        storage_key = f"original/{document.id}/{document.filename}"

        # Store in MinIO
        await self.storage_client.store_file(
            key=storage_key,
            content=document.content,
            content_type=document.content_type
        )

        # Update document with storage information
        document.storage_key = storage_key
        document.storage_bucket = self.config.minio_bucket

        # Save document to database
        await self.save_document(document)

    async def _parse_pdf_with_mineru(self, document: Document, task_id: str) -> Dict[str, Any]:
        """
        Parse PDF using MinerU adapter.
        """
        self.logger.info(f"Parsing document {document.id} with MinerU for task {task_id}")

        # Get the file from storage (or use direct content for small files)
        if document.content and len(document.content) < self.config.mineru_direct_parse_threshold:
            # Use direct content for small files
            parsed_result = await self.mineru_adapter.parse_pdf_bytes(document.content)
        else:
            # Download from storage for larger files
            file_content = await self.storage_client.get_file(document.storage_key)
            parsed_result = await self.mineru_adapter.parse_pdf_bytes(file_content)

        return parsed_result

    async def _extract_evidence(self, parsed_content: Dict[str, Any], task_id: str) -> List[Any]:
        """
        Extract evidence from parsed content using agent workflow.

        Note: This is a placeholder implementation. The actual evidence extraction
        would be handled by the DataProcessingService and agent workflow.
        """
        self.logger.info(f"Extracting evidence for task {task_id}")

        # Simulate evidence extraction
        # In a real implementation, this would call the agent workflow
        evidence_items = []

        # Log the parsing result for debugging
        self.logger.debug(f"Parsed content keys: {list(parsed_content.keys())}")

        return evidence_items

    async def _finalize_task(self, task_id: str, document: Document, evidence_items: List[Any]) -> None:
        """
        Finalize the task by storing evidence items and updating document status.
        """
        self.logger.info(f"Finalizing task {task_id}")

        # Update document with evidence count
        document.evidence_count = len(evidence_items)
        document.processed_at = datetime.utcnow()
        document.status = "processed"

        # Save updated document
        await self.save_document(document)

        # Store evidence items (this would be implemented in evidence repository)
        # For now, we'll just log the count
        self.logger.info(f"Stored {len(evidence_items)} evidence items for document {document.id}")

    async def _update_task_status(
        self,
        task_id: str,
        status: str,
        progress: int,
        stage: str,
        error_message: str | None = None,
    ) -> None:
        """
        Update the task status in the database.
        """
        task_uuid = task_id if isinstance(task_id, UUID) else UUID(str(task_id))
        async with db_session_factory.get_session_context() as session:
            repository = TaskRepositoryImpl(session)
            await repository.update_status(task_uuid, status, progress, stage, error_message)

    async def _handle_task_failure(self, task_id: str, error_message: str) -> None:
        """
        Handle task failure by updating status and logging the error.
        """
        self.logger.error(f"Handling task failure for {task_id}: {error_message}")
        await self._update_task_status(task_id, "failed", 0, "Failed", error_message)

    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the current status of a parsing task.
        """
        return await self.task_management_service.get_task_status(task_id)

    async def get_task_progress(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get real-time progress information for a parsing task.
        """
        return await self.task_management_service.get_task_progress(task_id)

    async def retry_task(self, task_id: str) -> bool:
        """
        Retry a failed parsing task.
        """
        return await self.task_management_service.retry_task(task_id)

    async def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a pending or processing parsing task.
        """
        return await self.task_management_service.cancel_task(task_id)

    def validate_pmid(self, pmid: str) -> bool:
        """
        Validate PMID format (1-8 digits).
        """
        return bool(re.match(r'^\d{1,8}$', pmid))

    def validate_doi(self, doi: str) -> bool:
        """
        Validate DOI format.
        """
        return bool(re.match(r'^10\.\d{4,9}/[-._;()/:A-Z0-9]+$', doi, re.IGNORECASE))

    def perform_service(self, *args, **kwargs):
        """Abstract method implementation - not used in this service."""
        pass

    def _resolve_source(self, upload_request: Any) -> UploadSource:
        """Normalize the source on dynamic upload request objects."""
        source_value = getattr(upload_request, "source", UploadSource.FILE)
        if isinstance(source_value, UploadSource):
            return source_value
        if isinstance(source_value, str):
            try:
                return UploadSource(source_value.lower())
            except ValueError:
                return UploadSource.FILE
        return UploadSource.FILE
