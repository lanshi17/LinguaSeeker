"""PostgreSQL database models using SQLAlchemy ORM.

This module defines all database tables for the ACMG Intelligence System.
Models follow the data model specification in design_docs/data-model.md.
"""

import enum
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


# Enums
class ProcessingStatus(str, enum.Enum):
    """Document processing status."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class ACMGCode(str, enum.Enum):
    """ACMG evidence codes."""

    # Pathogenic Strong
    PS1 = "PS1"
    PS2 = "PS2"
    PS3 = "PS3"
    PS4 = "PS4"
    # Pathogenic Moderate
    PM1 = "PM1"
    PM2 = "PM2"
    PM3 = "PM3"
    PM4 = "PM4"
    PM5 = "PM5"
    PM6 = "PM6"
    # Pathogenic Supporting
    PP1 = "PP1"
    PP2 = "PP2"
    PP3 = "PP3"
    PP4 = "PP4"
    PP5 = "PP5"
    # Benign Stand-alone
    BA1 = "BA1"
    # Benign Strong
    BS1 = "BS1"
    BS2 = "BS2"
    BS3 = "BS3"
    BS4 = "BS4"
    # Benign Supporting
    BP1 = "BP1"
    BP2 = "BP2"
    BP3 = "BP3"
    BP4 = "BP4"
    BP5 = "BP5"
    BP6 = "BP6"
    BP7 = "BP7"


class TaskStatus(str, enum.Enum):
    """Task execution status."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRY = "RETRY"


class TaskStage(str, enum.Enum):
    """Task processing stages."""

    INGESTION = "INGESTION"
    DECOMPOSITION = "DECOMPOSITION"
    LAYOUT = "LAYOUT"
    TRANSLATION = "TRANSLATION"
    EVIDENCE = "EVIDENCE"
    ARBITRATION = "ARBITRATION"
    COMPLETED = "COMPLETED"


class TaskType(str, enum.Enum):
    """Parsing task type based on ingestion mode."""

    PDF_PARSE = "pdf_parse"
    IDENTIFIER_RESOLVE = "identifier_resolve"
    DATA_EXTRACTION = "data_extraction"


class AgentType(str, enum.Enum):
    """Agent types in the workflow."""

    LAYOUT = "LAYOUT"
    TRANSLATION = "TRANSLATION"
    EVIDENCE = "EVIDENCE"
    ARBITRATION = "ARBITRATION"


class SourceLanguage(str, enum.Enum):
    """Source languages."""

    EN = "EN"
    ZH = "ZH"


class PathogenicityClassification(str, enum.Enum):
    """Variant pathogenicity classification."""

    BENIGN = "BENIGN"
    LIKELY_BENIGN = "LIKELY_BENIGN"
    VUS = "VUS"
    LIKELY_PATHOGENIC = "LIKELY_PATHOGENIC"
    PATHOGENIC = "PATHOGENIC"
    CONFLICTING = "CONFLICTING"


class PhenotypeSeverity(str, enum.Enum):
    """Phenotype severity levels."""

    MILD = "MILD"
    MODERATE = "MODERATE"
    SEVERE = "SEVERE"
    PROFOUND = "PROFOUND"


class SagaStatus(str, enum.Enum):
    """Saga operation status."""

    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    COMPENSATED = "COMPENSATED"


class TargetStore(str, enum.Enum):
    """Target storage systems."""

    MINIO = "MINIO"
    POSTGRES = "POSTGRES"
    NEO4J = "NEO4J"
    QDRANT = "QDRANT"


# Models


class Document(Base):
    """Biomedical research paper document."""

    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    title = Column(String(500), nullable=False)
    authors = Column(JSONB, nullable=False, default=list)
    journal = Column(String(200), nullable=True)
    publication_date = Column(DateTime(timezone=True), nullable=True)
    pmid = Column(String(50), nullable=True)
    doi = Column(String(200), nullable=True)
    content_hash = Column(String(64), nullable=False, unique=True)
    file_size_bytes = Column(Integer, nullable=False)
    page_count = Column(Integer, nullable=False)
    storage_path = Column(String(500), nullable=False)
    processing_status = Column(
        Enum(ProcessingStatus), nullable=False, default=ProcessingStatus.PENDING
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    evidence_items = relationship("EvidenceItem", back_populates="document")
    translation_pairs = relationship("TranslationPair", back_populates="document")
    parsing_task = relationship("ParsingTask", back_populates="document", uselist=False)

    __table_args__ = (
        Index("idx_documents_content_hash", "content_hash"),
        Index("idx_documents_pmid", "pmid"),
        Index("idx_documents_doi", "doi"),
        Index("idx_documents_status", "processing_status"),
        Index("idx_documents_created_at", "created_at"),
    )


class EvidenceItem(Base):
    """ACMG evidence criterion extracted from a document."""

    __tablename__ = "evidence_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    acmg_code = Column(Enum(ACMGCode), nullable=False)
    confidence_score = Column(Numeric(3, 2), nullable=False)
    source_page = Column(Integer, nullable=False)
    bounding_box = Column(JSONB, nullable=False)
    source_hash = Column(String(64), nullable=False)
    supporting_text = Column(Text, nullable=False)
    review_required = Column(Boolean, nullable=False, default=False)
    human_reviewed = Column(Boolean, nullable=False, default=False)
    human_notes = Column(Text, nullable=True)
    variant_id = Column(UUID(as_uuid=True), ForeignKey("variants.id"), nullable=True)
    extracted_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    document = relationship("Document", back_populates="evidence_items")
    variant = relationship("Variant", back_populates="evidence_items")

    __table_args__ = (
        Index("idx_evidence_document_id", "document_id"),
        Index("idx_evidence_variant_id", "variant_id"),
        Index("idx_evidence_review_required", "review_required"),
        Index("idx_evidence_human_reviewed", "human_reviewed"),
        Index("idx_evidence_acmg_code", "acmg_code"),
        Index("idx_evidence_confidence_score", "confidence_score"),
        Index("idx_evidence_extracted_at", "extracted_at"),
    )


class TranslationPair(Base):
    """Aligned bilingual text segments from a document."""

    __tablename__ = "translation_pairs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    paragraph_index = Column(Integer, nullable=False)
    source_language = Column(Enum(SourceLanguage), nullable=False)
    source_text = Column(Text, nullable=False)
    target_text = Column(Text, nullable=False)
    source_page = Column(Integer, nullable=False)
    source_coordinates = Column(JSONB, nullable=False)
    alignment_confidence = Column(Numeric(3, 2), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    document = relationship("Document", back_populates="translation_pairs")

    __table_args__ = (
        Index("idx_translation_document_id", "document_id"),
        Index("idx_translation_paragraph", "document_id", "paragraph_index"),
    )


class Variant(Base):
    """Genetic variant mentioned in documents."""

    __tablename__ = "variants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    hgvs_notation = Column(String(200), nullable=False, unique=True)
    gene = Column(String(50), nullable=False)
    chromosome = Column(String(5), nullable=False)
    position = Column(Integer, nullable=False)
    reference_allele = Column(String(1000), nullable=False)
    alternate_allele = Column(String(1000), nullable=False)
    pathogenicity_classification = Column(
        Enum(PathogenicityClassification), nullable=False
    )
    aggregated_confidence = Column(Numeric(3, 2), nullable=False)
    evidence_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    evidence_items = relationship("EvidenceItem", back_populates="variant")

    __table_args__ = (
        Index("idx_variants_hgvs", "hgvs_notation"),
        Index("idx_variants_gene", "gene"),
        Index("idx_variants_chromosome", "chromosome"),
        Index("idx_variants_classification", "pathogenicity_classification"),
    )


class Phenotype(Base):
    """Clinical phenotype associated with variants."""

    __tablename__ = "phenotypes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    hpo_code = Column(String(20), nullable=False, unique=True)
    description = Column(String(500), nullable=False)
    severity = Column(Enum(PhenotypeSeverity), nullable=False)
    affected_system = Column(String(100), nullable=False)
    prevalence = Column(Numeric(5, 4), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_phenotypes_hpo", "hpo_code"),
        Index("idx_phenotypes_severity", "severity"),
        Index("idx_phenotypes_system", "affected_system"),
    )


class ParsingTask(Base):
    """Asynchronous document processing task."""

    __tablename__ = "parsing_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "documents.id",
            ondelete="SET NULL",
            deferrable=True,
            initially="IMMEDIATE",
        ),
        nullable=True,
        unique=True,
    )
    task_type = Column(Enum(TaskType), nullable=False, default=TaskType.PDF_PARSE)
    current_stage = Column(Enum(TaskStage), nullable=False, default=TaskStage.INGESTION)
    progress_percentage = Column(Integer, nullable=False, default=0)
    status = Column(Enum(TaskStatus), nullable=False, default=TaskStatus.PENDING)
    priority = Column(Integer, nullable=False, default=5)
    retry_count = Column(Integer, nullable=False, default=0)
    failure_reason = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    estimated_completion = Column(DateTime, nullable=True)

    # Relationships
    document = relationship("Document", back_populates="parsing_task")
    audit_logs = relationship("AuditLogEntry", back_populates="task")

    __table_args__ = (
        Index("idx_tasks_document_id", "document_id"),
        Index("idx_tasks_status", "status"),
        Index("idx_tasks_stage", "current_stage"),
        Index("idx_tasks_type", "task_type"),
        Index("idx_tasks_priority", "priority"),
        Index("idx_tasks_created_at", "created_at"),
        Index("idx_tasks_started_at", "started_at"),
    )


class AuditLogEntry(Base):
    """Immutable record of agent decision-making."""

    __tablename__ = "audit_log_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("parsing_tasks.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    agent_type = Column(Enum(AgentType), nullable=False)
    state_from = Column(String(50), nullable=False)
    state_to = Column(String(50), nullable=False)
    confidence_score = Column(Numeric(3, 2), nullable=True)
    latency_ms = Column(Integer, nullable=False)
    input_prompt = Column(Text, nullable=False)
    output_reasoning = Column(Text, nullable=False)
    failure_reason = Column(Text, nullable=True)
    model_version = Column(String(50), nullable=False)
    token_count = Column(Integer, nullable=True)

    # Relationships
    task = relationship("ParsingTask", back_populates="audit_logs")

    __table_args__ = (
        Index("idx_audit_task_id", "task_id"),
        Index("idx_audit_agent_type", "agent_type"),
        Index("idx_audit_state_to", "state_to"),
        Index("idx_audit_created_at", "created_at"),
        Index("idx_audit_latency", "latency_ms"),
    )


class AgentCache(Base):
    """Cache for agent outputs to prevent redundant LLM calls."""

    __tablename__ = "agent_cache"

    input_hash = Column(String(64), primary_key=True)
    agent_type = Column(Enum(AgentType), nullable=False)
    model_version = Column(String(50), nullable=False)
    output = Column(JSONB, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    hit_count = Column(Integer, nullable=False, default=0)

    __table_args__ = (
        Index("idx_cache_agent_type", "agent_type"),
        Index("idx_cache_model_version", "model_version"),
        Index("idx_cache_created_at", "created_at"),
    )


class StorageOperation(Base):
    """Multi-store saga operation log."""

    __tablename__ = "storage_operations"

    saga_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("parsing_tasks.id"), nullable=False)
    step_name = Column(String(100), nullable=False)
    status = Column(Enum(SagaStatus), nullable=False, default=SagaStatus.PENDING)
    target_store = Column(Enum(TargetStore), nullable=False)
    operation_data = Column(JSONB, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_saga_task_id", "task_id"),
        Index("idx_saga_status", "status"),
        Index("idx_saga_target_store", "target_store"),
        Index("idx_saga_created_at", "created_at"),
    )
