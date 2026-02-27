from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
	Column,
	Date,
	DateTime,
	Float,
	ForeignKey,
	Index,
	Integer,
	BigInteger,
	String,
	Text,
	UniqueConstraint,
	func,
	text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import declarative_base, relationship

from src.database.enum import MinioBucketNameEnum

Base = declarative_base()


class User(Base):
	__tablename__ = "users"

	id = Column(Integer, primary_key=True, autoincrement=True)
	username = Column(String(100), nullable=False)
	email = Column(String(255), nullable=False)
	created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

	__table_args__ = (
		UniqueConstraint("username", name="uq_users_username"),
		UniqueConstraint("email", name="uq_users_email"),
	)


class Document(Base):
	__tablename__ = "documents"

	document_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
	title = Column(String(500), nullable=False)
	original_filename = Column(String(500), nullable=True)
	pmid = Column(String(64), nullable=True)
	local_path = Column(Text, nullable=True)
	file_hash = Column(String(64), nullable=False)
	status = Column(String(50), nullable=False, default="pending")
	summary = Column(Text, nullable=True)
	created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
	updated_at = Column(
		DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
	)

	tasks = relationship("Task", back_populates="document", cascade="all, delete-orphan")
	entity_links = relationship(
		"EntityDocumentMapping", back_populates="document", cascade="all, delete-orphan"
	)

	__table_args__ = (
		Index("ix_documents_status", "status"),
		Index("ix_documents_pmid", "pmid"),
		Index("ix_documents_file_hash", "file_hash", unique=True),
	)


class Task(Base):
	__tablename__ = "tasks"

	task_id = Column(Integer, primary_key=True, autoincrement=True)
	document_id = Column(UUID(as_uuid=True), ForeignKey("documents.document_id"), nullable=False)
	task_type = Column("type", String(50), nullable=False)
	status = Column(String(50), nullable=False, default="pending")
	progress = Column(Float, nullable=True)
	result = Column(JSONB, nullable=True)
	created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
	updated_at = Column(
		DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
	)

	document = relationship("Document", back_populates="tasks")

	__table_args__ = (
		Index("ix_tasks_status", "status"),
		Index("ix_tasks_document_id", "document_id"),
	)


class TaskLog(Base):
	__tablename__ = "task_logs"

	log_id = Column(Integer, primary_key=True, autoincrement=True)
	task_id = Column(Integer, ForeignKey("tasks.task_id", ondelete="SET NULL"), nullable=True)
	document_id = Column(UUID(as_uuid=True), ForeignKey("documents.document_id", ondelete="CASCADE"), nullable=False)
	status = Column(String(50), nullable=False)
	category = Column(String(100), nullable=True)
	payload = Column(JSONB, nullable=True)
	missing_fields_detail = Column(JSONB, nullable=True)
	created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

	task = relationship("Task", backref="logs")

	__table_args__ = (
		Index("ix_task_logs_document_id", "document_id"),
		Index("ix_task_logs_status", "status"),
	)


class Entity(Base):
	__tablename__ = "entities"

	entity_id = Column(Integer, primary_key=True, autoincrement=True)
	entity_type = Column("type", String(100), nullable=False)
	name = Column(String(255), nullable=False)
	standardized_name = Column(String(255), nullable=True)
	entity_metadata = Column("metadata", JSONB, key="entity_metadata", nullable=True)

	document_links = relationship(
		"EntityDocumentMapping", back_populates="entity", cascade="all, delete-orphan"
	)

	__table_args__ = (
		UniqueConstraint("type", "name", name="uq_entities_type_name"),
		Index("ix_entities_name", "name"),
	)


class EntityDocumentMapping(Base):
	__tablename__ = "entity_document_mapping"

	document_id = Column(UUID(as_uuid=True), ForeignKey("documents.document_id"), primary_key=True)
	entity_id = Column(Integer, ForeignKey("entities.entity_id"), primary_key=True)
	confidence_score = Column(Float, nullable=True)
	mentions = Column(JSONB, nullable=True)

	document = relationship("Document", back_populates="entity_links")
	entity = relationship("Entity", back_populates="document_links")

	__table_args__ = (
		Index("ix_entity_document_mapping_document_id", "document_id"),
		Index("ix_entity_document_mapping_entity_id", "entity_id"),
	)


class GraphNodeCache(Base):
	__tablename__ = "graph_nodes_cache"

	cache_id = Column(Integer, primary_key=True, autoincrement=True)
	node_type = Column(String(100), nullable=False)
	neo4j_node_id = Column(Integer, nullable=False)
	name = Column(String(255), nullable=True)
	description = Column(Text, nullable=True)
	properties = Column(JSONB, nullable=True)

	__table_args__ = (
		UniqueConstraint("neo4j_node_id", name="uq_graph_nodes_cache_neo4j_node_id"),
		Index("ix_graph_nodes_cache_node_type", "node_type"),
	)


class GraphEdgeCache(Base):
	__tablename__ = "graph_edges_cache"

	cache_id = Column(Integer, primary_key=True, autoincrement=True)
	neo4j_relationship_id = Column(Integer, nullable=False)
	start_node_id = Column(Integer, nullable=False)
	end_node_id = Column(Integer, nullable=False)
	relationship_type = Column(String(100), nullable=False)
	properties = Column(JSONB, nullable=True)

	__table_args__ = (
		UniqueConstraint(
			"neo4j_relationship_id", name="uq_graph_edges_cache_neo4j_relationship_id"
		),
		Index("ix_graph_edges_cache_relationship_type", "relationship_type"),
		Index("ix_graph_edges_cache_start_node_id", "start_node_id"),
		Index("ix_graph_edges_cache_end_node_id", "end_node_id"),
	)


# ==================== ClinVar / ClinGen 扩展表 ====================

class ClinVarVariation(Base):
	__tablename__ = "clinvar_variations"

	variation_id = Column(BigInteger, primary_key=True)
	preferred_name = Column(String(1000), nullable=True)
	primary_hgvs = Column(String(1000), nullable=True)
	gene_symbol = Column(String(100), nullable=True)
	transcript_id = Column(String(100), nullable=True)
	clinvar_accession = Column(String(32), nullable=True)
	review_status = Column(String(200), nullable=True)
	clinical_significance = Column(String(200), nullable=True)
	last_evaluated_at = Column(DateTime(timezone=True), nullable=True)
	synonyms = Column(JSONB, nullable=True)
	hgvs_list = Column(JSONB, nullable=True)
	trait_names = Column(JSONB, nullable=True)
	attributes = Column(JSONB, nullable=True)
	citations_synced_at = Column(DateTime(timezone=True), nullable=True)
	scorecards_synced_at = Column(DateTime(timezone=True), nullable=True)
	created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
	updated_at = Column(
		DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
	)

	evidence_records = relationship("EvidenceRecord", back_populates="clinvar_variation")
	citations = relationship(
		"VariationCitation", back_populates="variation", cascade="all, delete-orphan"
	)
	scorecards = relationship(
		"ClinGenEvidenceProfile", back_populates="variation", cascade="all, delete-orphan"
	)

	__table_args__ = (
		Index("ix_clinvar_variations_gene_symbol", "gene_symbol"),
		Index("ix_clinvar_variations_primary_hgvs", "primary_hgvs"),
	)


class VariationCitation(Base):
	__tablename__ = "variation_citations"

	citation_id = Column(Integer, primary_key=True, autoincrement=True)
	variation_id = Column(
		BigInteger,
		ForeignKey("clinvar_variations.variation_id", ondelete="CASCADE"),
		nullable=False,
	)
	source = Column(String(50), nullable=False)
	pmid = Column(String(32), nullable=True)
	document_id = Column(
		UUID(as_uuid=True),
		ForeignKey("documents.document_id", ondelete="CASCADE"),
		nullable=True,
	)
	evidence_strength = Column(String(100), nullable=True)
	notes = Column(Text, nullable=True)
	citation_metadata = Column("metadata", JSONB, key="citation_metadata", nullable=True)
	created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

	variation = relationship("ClinVarVariation", back_populates="citations")
	document = relationship("Document")

	__table_args__ = (
		Index("ix_variation_citations_variation", "variation_id"),
		Index(
			"uq_variation_citations_pmid",
			"variation_id",
			"source",
			"pmid",
			unique=True,
			postgresql_where=text("pmid IS NOT NULL"),
		),
		Index(
			"uq_variation_citations_document",
			"variation_id",
			"source",
			"document_id",
			unique=True,
			postgresql_where=text("document_id IS NOT NULL"),
		),
	)


class ClinGenEvidenceProfile(Base):
	__tablename__ = "clingen_evidence_profiles"

	profile_id = Column(Integer, primary_key=True, autoincrement=True)
	variation_id = Column(
		BigInteger,
		ForeignKey("clinvar_variations.variation_id", ondelete="CASCADE"),
		nullable=False,
	)
	assertion_id = Column(String(200), nullable=False)
	disease_label = Column(String(500), nullable=True)
	disease_mondo = Column(String(100), nullable=True)
	expert_panel = Column(String(255), nullable=True)
	classification = Column(String(100), nullable=True)
	published_at = Column(Date, nullable=True)
	guideline_label = Column(String(500), nullable=True)
	evidence_codes = Column(JSONB, nullable=True)
	score_breakdown = Column(JSONB, nullable=True)
	raw_payload = Column(JSONB, nullable=True)
	created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
	updated_at = Column(
		DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
	)

	variation = relationship("ClinVarVariation", back_populates="scorecards")

	__table_args__ = (
		UniqueConstraint("variation_id", "assertion_id", name="uq_clingen_assertion"),
		Index("ix_clingen_variation", "variation_id"),
		Index("ix_clingen_disease_mondo", "disease_mondo"),
	)


# ==================== 证据强度分类表 ====================

class EvidenceRecord(Base):
	"""证据评估记录表"""
	__tablename__ = "evidence_records"

	evidence_id = Column(Integer, primary_key=True, autoincrement=True)
	document_id = Column(UUID(as_uuid=True), ForeignKey("documents.document_id"), nullable=False)
	gene_symbol = Column(String(100), nullable=True)
	variant_hgvs_c = Column(String(500), nullable=True)
	variant_hgvs_p = Column(String(500), nullable=True)
	protein_change = Column(String(500), nullable=True)
	clinvar_variation_id = Column(
		BigInteger, ForeignKey("clinvar_variations.variation_id"), nullable=True
	)
	transcript_id = Column(String(100), nullable=True)
	reference_genome = Column(String(50), nullable=True)
	disease_name = Column(String(500), nullable=True)
	icd10_code = Column(String(50), nullable=True)
	species = Column(String(100), nullable=True)
	phenotype = Column(Text, nullable=True)

	# 证据强度分类
	evidence_strength = Column(String(50), nullable=True)
	evidence_classification = Column(String(100), nullable=True)
	overall_confidence = Column(Float, nullable=True)
	arbitration_score = Column(Float, nullable=True)
	is_valid = Column(String(10), nullable=True, default="false")

	# ACMG 等级
	acmg_levels = Column(JSONB, nullable=True)

	# 原始提取数据
	extracted_fields = Column(JSONB, nullable=True)
	ps3_evidence = Column(JSONB, nullable=True)

	# 时间戳
	created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
	updated_at = Column(
		DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
	)

	document = relationship("Document", backref="evidence_records")
	clinvar_variation = relationship("ClinVarVariation", back_populates="evidence_records")

	__table_args__ = (
		Index("ix_evidence_gene_symbol", "gene_symbol"),
		Index("ix_evidence_variant_hgvs_c", "variant_hgvs_c"),
		Index("ix_evidence_variant_hgvs_p", "variant_hgvs_p"),
		Index("ix_evidence_protein_change", "protein_change"),
		Index("ix_evidence_disease_name", "disease_name"),
		Index("ix_evidence_icd10_code", "icd10_code"),
		Index("ix_evidence_strength", "evidence_strength"),
		Index("ix_evidence_classification", "evidence_classification"),
		Index("ix_evidence_document_id", "document_id"),
		Index("ix_evidence_gene_variant", "gene_symbol", "variant_hgvs_c"),
		Index("ix_evidence_gene_protein", "gene_symbol", "protein_change"),
		Index("ix_evidence_clinvar_variation_id", "clinvar_variation_id"),
	)


@dataclass(frozen=True)
class MinioObjectRefModel:
	bucket: MinioBucketNameEnum
	object_key: str
	content_type: Optional[str] = None
