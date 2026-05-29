"""PostgreSQL data access layer."""

from src.dao.postgresql.connection import (
    async_session_factory,
    build_async_engine,
    build_asyncpg_connect_args,
    get_async_session,
)
from src.dao.postgresql.contracts import AsyncpgConnectArgs
from src.dao.postgresql.models import (
    Base,
    CanonicalEvidenceItem,
    EntityMergeEvent,
    EvidenceEntityBinding,
    NormalizedEntity,
    PipelineRunState,
    ProcessingRun,
    ReviewAuditEvent,
    RunEvidenceItem,
    SourceDocument,
    SourceDocumentIdentifier,
    TerminologyAlias,
    TerminologyEmbedding,
    TerminologyEntry,
    TerminologyRelationship,
    User,
)
from src.dao.postgresql.search_index_repo import SearchIndexRepository, frontend_search_index
from src.dao.postgresql.vector_repo import VectorRepository

__all__ = [
    "AsyncpgConnectArgs",
    "Base",
    "CanonicalEvidenceItem",
    "EntityMergeEvent",
    "EvidenceEntityBinding",
    "NormalizedEntity",
    "PipelineRunState",
    "ProcessingRun",
    "ReviewAuditEvent",
    "RunEvidenceItem",
    "SearchIndexRepository",
    "SourceDocument",
    "SourceDocumentIdentifier",
    "TerminologyAlias",
    "TerminologyEmbedding",
    "TerminologyEntry",
    "TerminologyRelationship",
    "User",
    "VectorRepository",
    "async_session_factory",
    "build_async_engine",
    "build_asyncpg_connect_args",
    "frontend_search_index",
    "get_async_session",
]
