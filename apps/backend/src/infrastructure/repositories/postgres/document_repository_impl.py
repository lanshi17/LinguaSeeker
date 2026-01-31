"""PostgreSQL implementation of Document Repository.

Concrete implementation using SQLAlchemy for document persistence.
"""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from src.domain.interfaces.document_repository import DocumentRepository
from src.domain.models.document import Document, ProcessingStatus, Author
from src.infrastructure.database.postgres_models import (
    Document as DocumentModel,
    ProcessingStatus as ProcessingStatusEnum,
)


class DocumentRepositoryImpl(DocumentRepository):
    """PostgreSQL implementation of document repository."""

    def __init__(self, session: AsyncSession):
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    def _to_domain(self, model: DocumentModel) -> Document:
        """Convert database model to domain entity.

        Args:
            model: SQLAlchemy model

        Returns:
            Domain entity
        """
        authors = [
            Author(name=author.get("name"), affiliation=author.get("affiliation"))
            for author in (model.authors or [])
        ]

        return Document(
            id=model.id,
            title=model.title,
            authors=authors,
            journal=model.journal,
            publication_date=model.publication_date,
            pmid=model.pmid,
            doi=model.doi,
            content_hash=model.content_hash,
            file_size_bytes=model.file_size_bytes,
            page_count=model.page_count,
            storage_path=model.storage_path,
            processing_status=ProcessingStatus(model.processing_status.value),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_model(self, entity: Document) -> DocumentModel:
        """Convert domain entity to database model.

        Args:
            entity: Domain entity

        Returns:
            SQLAlchemy model
        """
        authors_data = [
            {"name": author.name, "affiliation": author.affiliation}
            for author in entity.authors
        ]

        return DocumentModel(
            id=entity.id,
            title=entity.title,
            authors=authors_data,
            journal=entity.journal,
            publication_date=entity.publication_date,
            pmid=entity.pmid,
            doi=entity.doi,
            content_hash=entity.content_hash,
            file_size_bytes=entity.file_size_bytes,
            page_count=entity.page_count,
            storage_path=entity.storage_path,
            processing_status=ProcessingStatusEnum(entity.processing_status.value),
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    async def save(self, document: Document) -> Document:
        """Save or update a document."""
        try:
            # Check if document exists
            stmt = select(DocumentModel).where(DocumentModel.id == document.id)
            result = await self.session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing
                existing.title = document.title
                existing.authors = [
                    {"name": a.name, "affiliation": a.affiliation}
                    for a in document.authors
                ]
                existing.journal = document.journal
                existing.publication_date = document.publication_date
                existing.pmid = document.pmid
                existing.doi = document.doi
                existing.file_size_bytes = document.file_size_bytes
                existing.page_count = document.page_count
                existing.storage_path = document.storage_path
                existing.processing_status = ProcessingStatusEnum(
                    document.processing_status.value
                )
                existing.updated_at = document.updated_at
            else:
                # Create new
                model = self._to_model(document)
                self.session.add(model)

            await self.session.commit()
            await self.session.refresh(existing if existing else model)
            return self._to_domain(existing if existing else model)

        except IntegrityError as e:
            await self.session.rollback()
            if "content_hash" in str(e):
                raise ValueError(f"Document with hash {document.content_hash} already exists")
            raise

    async def find_by_id(self, document_id: UUID) -> Optional[Document]:
        """Find document by ID."""
        stmt = select(DocumentModel).where(DocumentModel.id == document_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def find_by_content_hash(self, content_hash: str) -> Optional[Document]:
        """Find document by content hash."""
        stmt = select(DocumentModel).where(DocumentModel.content_hash == content_hash)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def find_by_pmid(self, pmid: str) -> Optional[Document]:
        """Find document by PubMed ID."""
        stmt = select(DocumentModel).where(DocumentModel.pmid == pmid)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def find_by_doi(self, doi: str) -> Optional[Document]:
        """Find document by DOI."""
        stmt = select(DocumentModel).where(DocumentModel.doi == doi)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def find_all(self, limit: int = 100, offset: int = 0) -> List[Document]:
        """Find all documents with pagination."""
        stmt = (
            select(DocumentModel)
            .order_by(DocumentModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return [self._to_domain(model) for model in models]

    async def find_by_status(
        self, status: str, limit: int = 100, offset: int = 0
    ) -> List[Document]:
        """Find documents by processing status."""
        stmt = (
            select(DocumentModel)
            .where(DocumentModel.processing_status == ProcessingStatusEnum(status))
            .order_by(DocumentModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return [self._to_domain(model) for model in models]

    async def delete(self, document_id: UUID) -> bool:
        """Delete a document."""
        stmt = select(DocumentModel).where(DocumentModel.id == document_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if model:
            await self.session.delete(model)
            await self.session.commit()
            return True
        return False

    async def exists(self, document_id: UUID) -> bool:
        """Check if document exists."""
        stmt = select(func.count()).select_from(DocumentModel).where(
            DocumentModel.id == document_id
        )
        result = await self.session.execute(stmt)
        count = result.scalar()
        return count > 0

    async def count(self) -> int:
        """Count total documents."""
        stmt = select(func.count()).select_from(DocumentModel)
        result = await self.session.execute(stmt)
        return result.scalar()

    async def count_by_status(self, status: str) -> int:
        """Count documents by status."""
        stmt = (
            select(func.count())
            .select_from(DocumentModel)
            .where(DocumentModel.processing_status == ProcessingStatusEnum(status))
        )
        result = await self.session.execute(stmt)
        return result.scalar()
