"""Document Repository interface.

Defines the contract for document persistence operations.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from src.domain.models.document import Document


class DocumentRepository(ABC):
    """Abstract repository for document persistence.

    Follows the Repository pattern to abstract persistence details
    from domain logic. Implementations handle database-specific concerns.
    """

    @abstractmethod
    async def save(self, document: Document) -> Document:
        """Save or update a document.

        Args:
            document: Document entity to persist

        Returns:
            Saved document with any generated fields populated

        Raises:
            DuplicateDocumentError: If content_hash already exists
            RepositoryError: For other persistence errors
        """
        pass

    @abstractmethod
    async def find_by_id(self, document_id: UUID) -> Optional[Document]:
        """Find document by ID.

        Args:
            document_id: Document UUID

        Returns:
            Document if found, None otherwise
        """
        pass

    @abstractmethod
    async def find_by_content_hash(self, content_hash: str) -> Optional[Document]:
        """Find document by content hash.

        Args:
            content_hash: SHA256 hash of document content

        Returns:
            Document if found, None otherwise
        """
        pass

    @abstractmethod
    async def find_by_pmid(self, pmid: str) -> Optional[Document]:
        """Find document by PubMed ID.

        Args:
            pmid: PubMed identifier

        Returns:
            Document if found, None otherwise
        """
        pass

    @abstractmethod
    async def find_by_doi(self, doi: str) -> Optional[Document]:
        """Find document by DOI.

        Args:
            doi: Digital Object Identifier

        Returns:
            Document if found, None otherwise
        """
        pass

    @abstractmethod
    async def find_all(
        self, limit: int = 100, offset: int = 0
    ) -> List[Document]:
        """Find all documents with pagination.

        Args:
            limit: Maximum number of documents to return
            offset: Number of documents to skip

        Returns:
            List of documents
        """
        pass

    @abstractmethod
    async def find_by_status(
        self, status: str, limit: int = 100, offset: int = 0
    ) -> List[Document]:
        """Find documents by processing status.

        Args:
            status: Processing status to filter by
            limit: Maximum number of documents to return
            offset: Number of documents to skip

        Returns:
            List of documents matching status
        """
        pass

    @abstractmethod
    async def delete(self, document_id: UUID) -> bool:
        """Delete a document.

        Args:
            document_id: Document UUID

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    async def exists(self, document_id: UUID) -> bool:
        """Check if document exists.

        Args:
            document_id: Document UUID

        Returns:
            True if exists, False otherwise
        """
        pass

    @abstractmethod
    async def count(self) -> int:
        """Count total documents.

        Returns:
            Total number of documents
        """
        pass

    @abstractmethod
    async def count_by_status(self, status: str) -> int:
        """Count documents by status.

        Args:
            status: Processing status

        Returns:
            Number of documents with given status
        """
        pass
