"""SQLAlchemy ORM models for the MVP persistence schema."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from pgvector.sqlalchemy import Vector


class Base(DeclarativeBase):
    """Base metadata registry for DAO models."""


class TimestampMixin:
    """Created/updated timestamp columns shared by mutable tables."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class SourceDocument(Base, TimestampMixin):
    """Stable source document root across processing runs."""

    __tablename__ = "source_documents"

    source_document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    raw_metadata: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    latest_processing_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("processing_runs.processing_run_id", use_alter=True),
        nullable=True,
    )
    original_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    translated_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_blocks: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    translated_blocks: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    source_language: Mapped[str | None] = mapped_column(String(16), nullable=True)

    identifiers: Mapped[list[SourceDocumentIdentifier]] = relationship(
        back_populates="source_document",
        cascade="all, delete-orphan",
        lazy="raise",
    )


class SourceDocumentIdentifier(Base, TimestampMixin):
    """External identifier registry for source-document deduplication."""

    __tablename__ = "source_document_identifiers"
    __table_args__ = (
        UniqueConstraint("identifier_type", "identifier_value", name="uq_source_document_identifiers_type_value"),
        Index("ix_source_document_identifiers_source_document_id", "source_document_id"),
    )

    source_document_identifier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    source_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_documents.source_document_id"),
        nullable=False,
    )
    identifier_type: Mapped[str] = mapped_column(String(64), nullable=False)
    identifier_value: Mapped[str] = mapped_column(Text, nullable=False)

    source_document: Mapped[SourceDocument] = relationship(back_populates="identifiers", lazy="raise")


class LiteratureProfile(Base, TimestampMixin):
    """Aggregated literature profile summarizing evidence extraction results."""

    __tablename__ = "literature_profiles"
    __table_args__ = (
        UniqueConstraint(
            "source_document_id",
            "owner_user_id",
            name="uq_literature_profiles_document_owner",
            postgresql_nulls_not_distinct=True,
        ),
        Index("ix_literature_profiles_pmid", "pmid"),
        Index("ix_literature_profiles_doi", "doi"),
        Index("ix_literature_profiles_owner_updated", "owner_user_id", text("updated_at DESC")),
        Index(
            "ix_literature_profiles_evidence_groups_gin",
            "evidence_groups",
            postgresql_using="gin",
        ),
        Index("ix_literature_profiles_review_status", "review_status"),
    )

    literature_profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_documents.source_document_id"),
        nullable=False,
    )
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=True,
    )
    pmid: Mapped[str | None] = mapped_column(Text, nullable=True)
    doi: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    authors: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'"))
    journal: Mapped[str | None] = mapped_column(Text, nullable=True)
    publication_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # evidence_groups schema (produced by LiteratureProfileRepository._build_evidence_groups):
    # [
    #   {
    #     "group_id": str,
    #     "summary": {
    #       "gene": str | None,
    #       "variant": str | None,
    #       "disease": str | None,
    #       "classification": str | None,
    #     },
    #     "avg_confidence": float | None,
    #     "field_count": int,
    #     "review_status": str,  # provisional | approved | corrected | rejected
    #     "fields": [
    #       {
    #         "canonical_evidence_id": str,
    #         "field_id": str,
    #         "field_name": str | None,
    #         "category": str | None,
    #         "value": str | None,
    #         "confidence": float | None,
    #         "status": str | None,
    #         "track": str | None,
    #       }
    #     ],
    #   }
    # ]
    evidence_groups: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'"))
    review_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="provisional", server_default=text("'provisional'")
    )
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    overall_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    total_evidence_fields: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    found_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    not_found_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    latest_processing_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


class User(Base, TimestampMixin):
    """Minimal auth user used for login and review ownership."""

    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("username", name="uq_users_username"),)

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")


class ProcessingRun(Base):
    """Reproducibility boundary for one pipeline execution."""

    __tablename__ = "processing_runs"
    __table_args__ = (
        Index("ix_processing_runs_source_document_id", "source_document_id"),
        Index("ix_processing_runs_owner_created", "owner_user_id", text("created_at DESC")),
    )

    processing_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_documents.source_document_id"),
        nullable=False,
    )
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=True,
    )
    parser_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    translation_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    extraction_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    standardization_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    fusion_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    config_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    input_artifacts: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    output_artifacts: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    run_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class NormalizedEntity(Base, TimestampMixin):
    """Shared dictionary for standardized and unmapped biomedical entities."""

    __tablename__ = "normalized_entities"
    __table_args__ = (
        Index(
            "uq_normalized_entities_standardized_external_id",
            "entity_type",
            "external_id",
            unique=True,
            postgresql_where=text("external_id IS NOT NULL AND standardization_status = 'standardized'"),
        ),
        Index(
            "uq_normalized_entities_unmapped_raw_text",
            "entity_type",
            "normalized_raw_text",
            unique=True,
            postgresql_where=text("standardization_status = 'unmapped'"),
        ),
        Index(
            "uq_normalized_entities_reviewed_unmappable_raw_text",
            "entity_type",
            "normalized_raw_text",
            unique=True,
            postgresql_where=text("standardization_status = 'reviewed_unmappable'"),
        ),
        Index("ix_normalized_entities_merged_into_entity_id", "merged_into_entity_id"),
    )

    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    normalized_raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    aliases: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    standardization_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unmapped")
    merged_into_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("normalized_entities.entity_id"),
        nullable=True,
    )
    raw_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)


class EntityMergeEvent(Base):
    """Audit trail for entity merge decisions."""

    __tablename__ = "entity_merge_events"
    __table_args__ = (
        Index("ix_entity_merge_events_from_entity_id", "from_entity_id"),
        Index("ix_entity_merge_events_to_entity_id", "to_entity_id"),
    )

    entity_merge_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    from_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("normalized_entities.entity_id"),
        nullable=False,
    )
    to_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("normalized_entities.entity_id"),
        nullable=False,
    )
    merge_reason: Mapped[str] = mapped_column(Text, nullable=False)
    merged_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=True,
    )
    merged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    raw_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)


class RunEvidenceItem(Base, TimestampMixin):
    """Versioned evidence item produced by one processing run."""

    __tablename__ = "run_evidence_items"
    __table_args__ = (
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_run_evidence_items_confidence_range"),
        Index("ix_run_evidence_items_processing_run_id", "processing_run_id"),
        Index("ix_run_evidence_items_source_document_id", "source_document_id"),
        Index("ix_run_evidence_items_owner_document", "owner_user_id", "source_document_id"),
    )

    run_evidence_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    processing_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("processing_runs.processing_run_id"),
        nullable=False,
    )
    source_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_documents.source_document_id"),
        nullable=False,
    )
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=True,
    )
    track: Mapped[str] = mapped_column(String(32), nullable=False)
    field_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    value: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    position_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    text_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    source_span: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    entity_scope_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    raw_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)


class EvidenceEntityBinding(Base, TimestampMixin):
    """Hyperedge-style relation between run evidence and normalized entities."""

    __tablename__ = "evidence_entity_bindings"
    __table_args__ = (
        Index("ix_evidence_entity_bindings_entity_type_entity_id", "entity_type", "entity_id"),
        Index("ix_evidence_entity_bindings_run_evidence_item_id_role", "run_evidence_item_id", "role"),
    )

    evidence_entity_binding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    run_evidence_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("run_evidence_items.run_evidence_item_id"),
        nullable=False,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("normalized_entities.entity_id"),
        nullable=False,
    )
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    binding_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_entity_text: Mapped[str | None] = mapped_column(Text, nullable=True)


class CanonicalEvidenceItem(Base, TimestampMixin):
    """Current-best canonical evidence record grouped across runs."""

    __tablename__ = "canonical_evidence_items"
    __table_args__ = (
        CheckConstraint(
            "current_best_confidence >= 0 AND current_best_confidence <= 1",
            name="ck_canonical_evidence_items_current_best_confidence_range",
        ),
        UniqueConstraint(
            "source_document_id",
            "owner_user_id",
            "field_id",
            "position_hash",
            "entity_scope_hash",
            name="uq_canonical_evidence_items_identity",
            postgresql_nulls_not_distinct=True,
        ),
        Index("ix_canonical_evidence_items_source_document_id", "source_document_id"),
        Index("ix_canonical_evidence_items_owner_document", "owner_user_id", "source_document_id"),
        Index("ix_canonical_evidence_items_current_best_run_evidence_id", "current_best_run_evidence_id"),
        Index(
            "ix_canonical_evidence_items_group_id",
            text("(active_payload ->> 'group_id')"),
        ),
        Index("ix_canonical_evidence_items_field_id", "field_id"),
    )

    canonical_evidence_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_documents.source_document_id"),
        nullable=False,
    )
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=True,
    )
    field_id: Mapped[str] = mapped_column(String(128), nullable=False)
    position_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    text_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_scope_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    current_best_run_evidence_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("run_evidence_items.run_evidence_item_id", use_alter=True),
        nullable=True,
    )
    current_best_status: Mapped[str] = mapped_column(String(32), nullable=False)
    current_best_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    conflict_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="provisional")
    active_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)


class TerminologyEntry(Base, TimestampMixin):
    """Unified reference entity imported from terminology databases."""

    __tablename__ = "terminology_entries"
    __table_args__ = (
        UniqueConstraint("source_db", "external_id", name="uq_terminology_entries_source_external_id"),
        Index("ix_terminology_entries_entity_type_normalized_name", "entity_type", "normalized_name"),
        Index("ix_terminology_entries_source_db", "source_db"),
        Index("ix_terminology_entries_external_id", "external_id"),
    )

    entry_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_db: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_name: Mapped[str] = mapped_column(Text, nullable=False)
    aliases: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    raw_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    version: Mapped[str] = mapped_column(String(128), nullable=False)

    embeddings: Mapped[list[TerminologyEmbedding]] = relationship(
        back_populates="entry", cascade="all, delete-orphan", lazy="raise"
    )


class TerminologyAlias(Base, TimestampMixin):
    """Indexed lookup alias for terminology matching."""

    __tablename__ = "terminology_aliases"
    __table_args__ = (
        UniqueConstraint(
            "entry_id",
            "normalized_alias",
            "alias_type",
            name="uq_terminology_aliases_entry_alias_type",
        ),
        Index("ix_terminology_aliases_lookup", "entity_type", "normalized_alias"),
        Index("ix_terminology_aliases_entry_id", "entry_id"),
    )

    alias_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("terminology_entries.entry_id"),
        nullable=False,
    )
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    alias_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_alias: Mapped[str] = mapped_column(Text, nullable=False)
    alias_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_db: Mapped[str] = mapped_column(String(64), nullable=False)


class TerminologyRelationship(Base, TimestampMixin):
    """Structured relationship between terminology entries or scalar assertions."""

    __tablename__ = "terminology_relationships"
    __table_args__ = (
        # NULLS NOT DISTINCT: treats NULL object_entry_id as equal,
        # preventing duplicate scalar assertions (NULL != NULL in standard unique constraints).
        UniqueConstraint(
            "subject_entry_id",
            "object_entry_id",
            "relationship_type",
            "source_db",
            name="uq_terminology_relationships_identity",
            postgresql_nulls_not_distinct=True,
        ),
        Index("ix_terminology_relationships_subject_type", "subject_entry_id", "relationship_type"),
        Index("ix_terminology_relationships_object_type", "object_entry_id", "relationship_type"),
    )

    relationship_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject_entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("terminology_entries.entry_id"),
        nullable=False,
    )
    object_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("terminology_entries.entry_id"),
        nullable=True,
    )
    relationship_type: Mapped[str] = mapped_column(String(96), nullable=False)
    source_db: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_level: Mapped[str | None] = mapped_column(String(96), nullable=True)
    raw_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)


class TerminologyEmbedding(Base, TimestampMixin):
    """pgvector embedding for terminology semantic retrieval."""

    __tablename__ = "terminology_embeddings"
    __table_args__ = (
        UniqueConstraint(
            "entry_id",
            "embedding_text_hash",
            "embedding_model",
            name="uq_terminology_embeddings_entry_text_model",
        ),
        Index("ix_terminology_embeddings_entity_type_model", "entity_type", "embedding_model"),
        Index("ix_terminology_embeddings_entry_id", "entry_id"),
    )

    embedding_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("terminology_entries.entry_id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_db: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    embedding_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_text_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(255), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1024), nullable=False)

    entry: Mapped[TerminologyEntry] = relationship(back_populates="embeddings", lazy="raise")


# ── Phase 4: review_audit_events, chat_sessions, chat_messages ────────────────


class ReviewAuditEvent(Base):
    """Audit trail for evidence review operations."""

    __tablename__ = "review_audit_events"
    __table_args__ = (
        Index(
            "ix_review_audit_events_canonical_created",
            "canonical_evidence_id",
            text("created_at DESC"),
        ),
        Index(
            "ix_review_audit_events_reviewer_created",
            "reviewer_id",
            text("created_at DESC"),
        ),
    )

    review_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    canonical_evidence_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_evidence_items.canonical_evidence_id"),
        nullable=False,
    )
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=True,
    )
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    old_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    new_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    field_deltas: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ChatSession(Base, TimestampMixin):
    """Chat session optionally bound to a processing run."""

    __tablename__ = "chat_sessions"
    __table_args__ = (
        Index(
            "ix_chat_sessions_run_created",
            "processing_run_id",
            text("created_at DESC"),
        ),
    )

    chat_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    processing_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("processing_runs.processing_run_id"),
        nullable=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=True,
    )
    title: Mapped[str | None] = mapped_column(Text, nullable=True)


class ChatMessage(Base):
    """Chat message in a session."""

    __tablename__ = "chat_messages"
    __table_args__ = (Index("ix_chat_messages_session_created", "chat_session_id", "created_at"),)

    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    chat_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.chat_session_id"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_evidence_items.canonical_evidence_id"),
        nullable=True,
    )
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("normalized_entities.entity_id"),
        nullable=True,
    )
    action: Mapped[dict[str, object] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class PipelineRunState(Base):
    """Checkpoint persistence for pipeline orchestrator state.

    Stores the full PipelineGraphState as JSONB after each phase completes.
    Enables crash recovery by reloading state from the last checkpoint.
    """

    __tablename__ = "pipeline_run_states"
    __table_args__ = (
        Index("ix_pipeline_run_states_source_document_id", "source_document_id"),
        Index("ix_pipeline_run_states_pipeline_status", "pipeline_status"),
        Index("ix_pipeline_run_states_owner_created", "owner_user_id", text("created_at DESC")),
        Index("ix_pipeline_run_states_owner_heartbeat", "owner_worker_id", "heartbeat_at"),
        Index(
            "ux_pipeline_run_states_active_source_key",
            "owner_user_id",
            "source_key",
            unique=True,
            postgresql_nulls_not_distinct=True,
            postgresql_where=text("source_key IS NOT NULL AND pipeline_status IN ('pending', 'running')"),
        ),
    )

    processing_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    source_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_documents.source_document_id"),
        nullable=False,
    )
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=True,
    )
    state_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    pipeline_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", server_default=text("'pending'")
    )
    last_completed_stage: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Reserved: not yet populated by state_persistence.py.
    # Intended for crash-recovery triage (e.g., "phase_2_standardization").
    # Derivable from state_json phase statuses when needed.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    # Durable worker lease fields for multi-worker coordination
    source_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_worker_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PipelineJob(Base):
    """Persistent job queue for pipeline execution.

    Guarantees single-running-task invariant via SELECT FOR UPDATE SKIP LOCKED
    claim pattern. Jobs transition through: queued → running → completed/failed.
    Failed jobs can be retried by resetting status back to 'queued'.
    """

    __tablename__ = "pipeline_jobs"
    __table_args__ = (
        Index("ix_pipeline_jobs_status_priority", "status", "priority", "created_at"),
        Index("ix_pipeline_jobs_processing_run_id", "processing_run_id"),
        Index("ix_pipeline_jobs_owner_status", "owner_user_id", "status", "created_at"),
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed')",
            name="ck_pipeline_jobs_status",
        ),
    )

    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    processing_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued", server_default=text("'queued'"))
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_data: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    worker_id: Mapped[str | None] = mapped_column(String(128), nullable=True)


class DocumentProcessingCache(Base):
    """L2 PostgreSQL cache for document processing results.

    Stores the final PipelineGraphState (as JSONB) keyed by content_hash,
    so re-submission of the same document (identical bytes or identical
    source key + extraction target) returns the prior result without
    re-running the pipeline.
    """

    __tablename__ = "document_processing_cache"
    __table_args__ = (Index("ix_document_processing_cache_created_at", "created_at"),)

    cache_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    source_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    processing_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("source_documents.source_document_id"), nullable=False
    )
    result_state: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class DocumentAnnotation(Base, TimestampMixin):
    """User-created text-selection annotation on a rendered document paragraph.

    Stores character-offset spans over the flattened visible text of a
    paragraph (``original`` or ``translated`` track). The backend stores raw
    offset numbers without interpreting the coordinate system — the frontend
    owns offset semantics.
    """

    __tablename__ = "document_annotations"
    __table_args__ = (
        CheckConstraint(
            "end_offset > start_offset AND start_offset >= 0",
            name="ck_document_annotations_offsets_valid",
        ),
        Index("ix_document_annotations_doc_track", "source_document_id", "track"),
        Index("ix_document_annotations_owner_doc_track", "owner_user_id", "source_document_id", "track"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_documents.source_document_id"),
        nullable=False,
    )
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=True,
    )
    track: Mapped[str] = mapped_column(String(16), nullable=False)
    paragraph_id: Mapped[str] = mapped_column(String(128), nullable=False)
    start_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    end_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    color: Mapped[str | None] = mapped_column(String(16), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    author: Mapped[str | None] = mapped_column(String(128), nullable=True)
