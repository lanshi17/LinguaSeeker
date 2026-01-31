"""Document domain entity.

Rich domain model representing a biomedical research paper with business logic.
Separate from database models (postgres_models.py) and DTOs (presentation layer).
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4


class ProcessingStatus(str, Enum):
    """Document processing status."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


@dataclass
class Author:
    """Document author information."""

    name: str
    affiliation: Optional[str] = None


@dataclass
class Document:
    """Domain entity representing a biomedical research paper.

    This is a rich domain model that encapsulates business logic and validation.
    It is independent of database implementation and presentation concerns.
    """

    id: UUID = field(default_factory=uuid4)
    title: str = ""
    authors: List[Author] = field(default_factory=list)
    journal: Optional[str] = None
    publication_date: Optional[datetime] = None
    pmid: Optional[str] = None
    doi: Optional[str] = None
    content_hash: str = ""
    file_size_bytes: int = 0
    page_count: int = 0
    storage_path: str = ""
    processing_status: ProcessingStatus = ProcessingStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        """Validate document after initialization."""
        self._validate()

    def _validate(self) -> None:
        """Validate document invariants."""
        if self.file_size_bytes > 104_857_600:  # 100MB
            raise ValueError(
                f"File size {self.file_size_bytes} exceeds 100MB limit"
            )

        if self.page_count < 0:
            raise ValueError(f"Page count {self.page_count} must be positive")

        if not self.content_hash:
            raise ValueError("Content hash is required")

        if len(self.content_hash) != 64:
            raise ValueError("Content hash must be SHA256 (64 characters)")

    def start_processing(self) -> None:
        """Mark document as being processed."""
        if self.processing_status != ProcessingStatus.PENDING:
            raise ValueError(
                f"Cannot start processing document in status {self.processing_status}"
            )
        self.processing_status = ProcessingStatus.PROCESSING
        self.updated_at = datetime.utcnow()

    def complete_processing(self) -> None:
        """Mark document processing as completed."""
        if self.processing_status != ProcessingStatus.PROCESSING:
            raise ValueError(
                f"Cannot complete document not in PROCESSING status (current: {self.processing_status})"
            )
        self.processing_status = ProcessingStatus.COMPLETED
        self.updated_at = datetime.utcnow()

    def fail_processing(self) -> None:
        """Mark document processing as failed."""
        if self.processing_status not in [
            ProcessingStatus.PENDING,
            ProcessingStatus.PROCESSING,
        ]:
            raise ValueError(
                f"Cannot fail document in status {self.processing_status}"
            )
        self.processing_status = ProcessingStatus.FAILED
        self.updated_at = datetime.utcnow()

    def mark_needs_review(self) -> None:
        """Mark document as needing human review."""
        if self.processing_status not in [
            ProcessingStatus.PROCESSING,
            ProcessingStatus.COMPLETED,
        ]:
            raise ValueError(
                f"Cannot mark for review document in status {self.processing_status}"
            )
        self.processing_status = ProcessingStatus.NEEDS_REVIEW
        self.updated_at = datetime.utcnow()

    def is_processed(self) -> bool:
        """Check if document has been successfully processed."""
        return self.processing_status == ProcessingStatus.COMPLETED

    def is_failed(self) -> bool:
        """Check if document processing has failed."""
        return self.processing_status == ProcessingStatus.FAILED

    def needs_review(self) -> bool:
        """Check if document needs human review."""
        return self.processing_status == ProcessingStatus.NEEDS_REVIEW

    def has_identifier(self) -> bool:
        """Check if document has PMID or DOI."""
        return self.pmid is not None or self.doi is not None

    def get_identifier(self) -> str:
        """Get document identifier (PMID or DOI)."""
        if self.pmid:
            return f"PMID:{self.pmid}"
        if self.doi:
            return f"DOI:{self.doi}"
        return f"ID:{self.id}"

    def update_metadata(
        self,
        title: Optional[str] = None,
        authors: Optional[List[Author]] = None,
        journal: Optional[str] = None,
        publication_date: Optional[datetime] = None,
    ) -> None:
        """Update document metadata."""
        if title is not None:
            self.title = title
        if authors is not None:
            self.authors = authors
        if journal is not None:
            self.journal = journal
        if publication_date is not None:
            self.publication_date = publication_date
        self.updated_at = datetime.utcnow()

    def __repr__(self) -> str:
        """String representation of document."""
        return (
            f"Document(id={self.id}, title='{self.title[:50]}...', "
            f"status={self.processing_status})"
        )
