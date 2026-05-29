"""PostgreSQL data access layer.

Exports are available via ``from src.dao.postgresql import <name>`` for convenience,
but importing specific submodules directly (e.g. ``from src.dao.postgresql.models
import Base``) is preferred to avoid loading unnecessary dependencies.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
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
        ChatMessage,
        ChatSession,
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
    "ChatMessage",
    "ChatSession",
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


def __getattr__(name: str):  # type: ignore[no-untyped-def]
    """Lazy-load exports on first access to avoid eager pgvector dependency."""
    import importlib

    _lazy_imports: dict[str, str] = {
        "async_session_factory": "src.dao.postgresql.connection",
        "build_async_engine": "src.dao.postgresql.connection",
        "build_asyncpg_connect_args": "src.dao.postgresql.connection",
        "get_async_session": "src.dao.postgresql.connection",
        "AsyncpgConnectArgs": "src.dao.postgresql.contracts",
        "Base": "src.dao.postgresql.models",
        "CanonicalEvidenceItem": "src.dao.postgresql.models",
        "ChatMessage": "src.dao.postgresql.models",
        "ChatSession": "src.dao.postgresql.models",
        "EntityMergeEvent": "src.dao.postgresql.models",
        "EvidenceEntityBinding": "src.dao.postgresql.models",
        "NormalizedEntity": "src.dao.postgresql.models",
        "PipelineRunState": "src.dao.postgresql.models",
        "ProcessingRun": "src.dao.postgresql.models",
        "ReviewAuditEvent": "src.dao.postgresql.models",
        "RunEvidenceItem": "src.dao.postgresql.models",
        "SourceDocument": "src.dao.postgresql.models",
        "SourceDocumentIdentifier": "src.dao.postgresql.models",
        "TerminologyAlias": "src.dao.postgresql.models",
        "TerminologyEmbedding": "src.dao.postgresql.models",
        "TerminologyEntry": "src.dao.postgresql.models",
        "TerminologyRelationship": "src.dao.postgresql.models",
        "User": "src.dao.postgresql.models",
        "SearchIndexRepository": "src.dao.postgresql.search_index_repo",
        "frontend_search_index": "src.dao.postgresql.search_index_repo",
        "VectorRepository": "src.dao.postgresql.vector_repo",
    }

    if name in _lazy_imports:
        module = importlib.import_module(_lazy_imports[name])
        return getattr(module, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
