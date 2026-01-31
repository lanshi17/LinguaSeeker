"""Storage Orchestration Service.

Coordinates multi-store operations with saga pattern for consistency.
"""

from typing import Optional, Dict, Any
from uuid import UUID
import asyncio

from src.domain.interfaces.storage_client import StorageClient
from src.infrastructure.repositories.postgres.document_repository_impl import (
    DocumentRepositoryImpl,
)
from src.domain.models.document import Document


class StorageOrchestrationService:
    """Service for orchestrating multi-store operations.

    Implements saga pattern to maintain consistency across:
    - MinIO (object storage)
    - PostgreSQL (metadata)
    - Neo4j (knowledge graph)

    Provides rollback compensation for failed operations.
    """

    def __init__(
        self,
        storage_client: StorageClient,
        document_repository: DocumentRepositoryImpl,
    ):
        """Initialize storage orchestration service.

        Args:
            storage_client: MinIO storage client
            document_repository: Document repository
        """
        self.storage = storage_client
        self.doc_repo = document_repository

    async def store_document(
        self,
        document: Document,
        file_data: bytes,
        bucket: str = "acmg-documents",
    ) -> Document:
        """Store document with saga pattern.

        Saga steps:
        1. Upload to MinIO
        2. Save metadata to PostgreSQL
        3. (Rollback: delete from MinIO if step 2 fails)

        Args:
            document: Document entity
            file_data: PDF file bytes
            bucket: Storage bucket name

        Returns:
            Saved document entity

        Raises:
            StorageError: If operation fails
        """
        saga_id = document.id
        minio_uploaded = False

        try:
            # Step 1: Upload to MinIO
            from io import BytesIO

            file_stream = BytesIO(file_data)

            object_key = f"{document.content_hash}.pdf"
            await self.storage.upload_file(
                bucket=bucket,
                object_key=object_key,
                file_data=file_stream,
                content_type="application/pdf",
                metadata={
                    "document_id": str(document.id),
                    "content_hash": document.content_hash,
                },
            )

            # Update storage path
            document.storage_path = f"{bucket}/{object_key}"
            minio_uploaded = True

            # Step 2: Save to PostgreSQL
            saved_doc = await self.doc_repo.save(document)

            return saved_doc

        except Exception as e:
            # Compensation: rollback MinIO upload if PostgreSQL fails
            if minio_uploaded:
                try:
                    await self.storage.delete_file(bucket, object_key)
                except Exception as rollback_error:
                    # Log rollback failure but don't mask original error
                    print(f"Rollback failed: {rollback_error}")

            raise StorageError(f"Document storage failed: {e}")

    async def retrieve_document(
        self, document_id: UUID
    ) -> tuple[Document, Optional[bytes]]:
        """Retrieve document with file data.

        Args:
            document_id: Document UUID

        Returns:
            Tuple of (document entity, file bytes)

        Raises:
            DocumentNotFoundError: If document doesn't exist
        """
        # Get metadata from PostgreSQL
        document = await self.doc_repo.find_by_id(document_id)

        if not document:
            raise DocumentNotFoundError(f"Document {document_id} not found")

        # Parse storage path
        parts = document.storage_path.split("/", 1)
        if len(parts) != 2:
            raise StorageError(f"Invalid storage path: {document.storage_path}")

        bucket, object_key = parts

        # Download from MinIO
        try:
            file_data = await self.storage.download_file(bucket, object_key)
            return document, file_data.read()
        except Exception as e:
            raise StorageError(f"Failed to retrieve file: {e}")

    async def delete_document(self, document_id: UUID) -> bool:
        """Delete document from all stores.

        Args:
            document_id: Document UUID

        Returns:
            True if deleted successfully
        """
        # Get document metadata
        document = await self.doc_repo.find_by_id(document_id)

        if not document:
            return False

        # Parse storage path
        parts = document.storage_path.split("/", 1)
        if len(parts) != 2:
            raise StorageError(f"Invalid storage path: {document.storage_path}")

        bucket, object_key = parts

        # Delete from MinIO first (can be retried)
        await self.storage.delete_file(bucket, object_key)

        # Delete from PostgreSQL
        await self.doc_repo.delete(document_id)

        return True

    async def verify_consistency(self, document_id: UUID) -> Dict[str, bool]:
        """Verify document exists in all stores.

        Args:
            document_id: Document UUID

        Returns:
            Dictionary with store existence flags
        """
        result = {"postgres": False, "minio": False}

        # Check PostgreSQL
        document = await self.doc_repo.find_by_id(document_id)
        result["postgres"] = document is not None

        if document:
            # Check MinIO
            parts = document.storage_path.split("/", 1)
            if len(parts) == 2:
                bucket, object_key = parts
                result["minio"] = await self.storage.file_exists(bucket, object_key)

        return result


class StorageError(Exception):
    """Storage operation error."""

    pass


class DocumentNotFoundError(Exception):
    """Document not found error."""

    pass
