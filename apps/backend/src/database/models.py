from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import (
	Column,
	DateTime,
	Float,
	ForeignKey,
	Index,
	Integer,
	String,
	Text,
	UniqueConstraint,
	func,
)
from sqlalchemy.dialects.postgresql import JSONB
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

	document_id = Column(Integer, primary_key=True, autoincrement=True)
	title = Column(String(500), nullable=False)
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
	document_id = Column(Integer, ForeignKey("documents.document_id"), nullable=False)
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

	document_id = Column(Integer, ForeignKey("documents.document_id"), primary_key=True)
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


@dataclass(frozen=True)
class MinioObjectRefModel:
	bucket: MinioBucketNameEnum
	object_key: str
	content_type: Optional[str] = None
