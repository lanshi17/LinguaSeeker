from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, Iterable, List, Optional, Sequence, Union
from uuid import UUID
from urllib.parse import quote_plus

import psycopg2
from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

from src.config import settings as cfg
from src.database.models import (
	Base,
	Document,
	Entity,
	EntityDocumentMapping,
	EvidenceRecord,
	GraphEdgeCache,
	GraphNodeCache,
	Task,
	User,
)


def _build_database_url(db_name: Optional[str] = None) -> str:
	password = quote_plus(cfg.postgres_password or "")
	return str(
		URL.create(
			drivername="postgresql+psycopg2",
			username=cfg.postgres_user,
			password=password,
			host=cfg.postgres_host,
			port=cfg.postgres_port,
			database=db_name or cfg.postgres_db,
		)
	)


def _build_conninfo(db_name: Optional[str] = None) -> str:
	return (
		f"host={cfg.postgres_host} "
		f"port={cfg.postgres_port} "
		f"dbname={db_name or cfg.postgres_db} "
		f"user={cfg.postgres_user} "
		f"password={cfg.postgres_password}"
	)


def ensure_database_exists(db_name: Optional[str] = None) -> None:
	target_db = db_name or cfg.postgres_db
	conninfo = _build_conninfo("postgres")
	try:
		with psycopg2.connect(conninfo) as conn:
			conn.autocommit = True
			with conn.cursor() as cur:
				cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target_db,))
				exists = cur.fetchone()
				if not exists:
					cur.execute(f'CREATE DATABASE "{target_db}"')
					logger.info("Created PostgreSQL database: {}", target_db)
	except Exception as exc:
		logger.warning("Failed to ensure database exists: {}", exc)
		raise


def initialize_schema(db_name: Optional[str] = None, schema_name: Optional[str] = None) -> None:
	ensure_database_exists(db_name)
	engine = get_engine(db_name)
	if schema_name:
		engine = engine.execution_options(schema_translate_map={None: schema_name})
	Base.metadata.create_all(engine)


def get_engine(db_name: Optional[str] = None):
	conninfo = _build_conninfo(db_name)
	return create_engine(
		"postgresql+psycopg2://",
		creator=lambda: psycopg2.connect(conninfo),
		pool_size=cfg.postgres_pool_size,
		max_overflow=cfg.postgres_max_overflow,
		pool_pre_ping=True,
		future=True,
	)


class PostgresClient:
	def __init__(self, engine=None):
		self.engine = engine or get_engine()
		self.SessionLocal = sessionmaker(
			bind=self.engine,
			autocommit=False,
			autoflush=False,
			expire_on_commit=False,
			future=True,
		)

	@staticmethod
	def _coerce_uuid(value: Union[UUID, str]) -> UUID:
		if isinstance(value, UUID):
			return value
		return UUID(str(value))

	@contextmanager
	def session_scope(self) -> Iterable[Session]:
		session = self.SessionLocal()
		try:
			yield session
			session.commit()
		except Exception:
			session.rollback()
			raise
		finally:
			session.close()

	# -------------------- Users --------------------
	def create_user(self, username: str, email: str) -> User:
		with self.session_scope() as session:
			user = User(username=username, email=email)
			session.add(user)
			session.flush()
			return user

	def get_user_by_id(self, user_id: int) -> Optional[User]:
		with self.session_scope() as session:
			return session.get(User, user_id)

	def get_user_by_username(self, username: str) -> Optional[User]:
		with self.session_scope() as session:
			return session.query(User).filter(User.username == username).one_or_none()

	# -------------------- Documents --------------------
	def create_document(
		self,
		title: str,
		file_hash: str,
		document_id: Optional[UUID] = None,
		original_filename: Optional[str] = None,
		pmid: Optional[str] = None,
		local_path: Optional[str] = None,
		status: str = "pending",
		summary: Optional[str] = None,
	) -> Document:
		with self.session_scope() as session:
			doc_kwargs = {
				"title": title,
				"original_filename": original_filename,
				"pmid": pmid,
				"local_path": local_path,
				"file_hash": file_hash,
				"status": status,
				"summary": summary,
			}
			if document_id is not None:
				doc_kwargs["document_id"] = document_id
			document = Document(**doc_kwargs)
			session.add(document)
			session.flush()
			return document

	def get_document_by_id(self, document_id: UUID) -> Optional[Document]:
		document_id = self._coerce_uuid(document_id)
		with self.session_scope() as session:
			return session.get(Document, document_id)

	def get_document_by_pmid(self, pmid: str) -> Optional[Document]:
		with self.session_scope() as session:
			return session.query(Document).filter(Document.pmid == pmid).one_or_none()

	def find_document_by_hash(self, file_hash: str) -> Optional[Document]:
		with self.session_scope() as session:
			return (
				session.query(Document)
				.filter(Document.file_hash == file_hash)
				.one_or_none()
			)

	def list_documents(
		self,
		status: Optional[str] = None,
		limit: int = 100,
		offset: int = 0,
	) -> List[Document]:
		with self.session_scope() as session:
			query = session.query(Document)
			if status:
				query = query.filter(Document.status == status)
			return query.order_by(Document.document_id).offset(offset).limit(limit).all()

	def update_document(self, document_id: UUID, **fields: Any) -> Optional[Document]:
		document_id = self._coerce_uuid(document_id)
		with self.session_scope() as session:
			document = session.get(Document, document_id)
			if not document:
				return None
			for key, value in fields.items():
				if hasattr(document, key):
					setattr(document, key, value)
			session.flush()
			return document

	def delete_document(self, document_id: UUID) -> bool:
		document_id = self._coerce_uuid(document_id)
		with self.session_scope() as session:
			document = session.get(Document, document_id)
			if not document:
				return False
			session.delete(document)
			return True

	# -------------------- Tasks --------------------
	def create_task(
		self,
		document_id: UUID,
		task_type: str,
		status: str = "pending",
		progress: Optional[float] = None,
		result: Optional[Dict[str, Any]] = None,
	) -> Task:
		document_id = self._coerce_uuid(document_id)
		with self.session_scope() as session:
			task = Task(
				document_id=document_id,
				task_type=task_type,
				status=status,
				progress=progress,
				result=result,
			)
			session.add(task)
			session.flush()
			return task

	def get_task_by_id(self, task_id: int) -> Optional[Task]:
		with self.session_scope() as session:
			return session.get(Task, task_id)

	def list_tasks_by_document(self, document_id: UUID) -> List[Task]:
		document_id = self._coerce_uuid(document_id)
		with self.session_scope() as session:
			return (
				session.query(Task)
				.filter(Task.document_id == document_id)
				.order_by(Task.task_id)
				.all()
			)

	def update_task(self, task_id: int, **fields: Any) -> Optional[Task]:
		with self.session_scope() as session:
			task = session.get(Task, task_id)
			if not task:
				return None
			for key, value in fields.items():
				if hasattr(task, key):
					setattr(task, key, value)
			session.flush()
			return task

	def delete_task(self, task_id: int) -> bool:
		with self.session_scope() as session:
			task = session.get(Task, task_id)
			if not task:
				return False
			session.delete(task)
			return True

	# -------------------- Entities --------------------
	def create_entity(
		self,
		entity_type: str,
		name: str,
		standardized_name: Optional[str] = None,
		metadata: Optional[Dict[str, Any]] = None,
	) -> Entity:
		with self.session_scope() as session:
			entity = Entity(
				entity_type=entity_type,
				name=name,
				standardized_name=standardized_name,
				entity_metadata=metadata,
			)
			session.add(entity)
			session.flush()
			return entity

	def get_entity_by_id(self, entity_id: int) -> Optional[Entity]:
		with self.session_scope() as session:
			return session.get(Entity, entity_id)

	def get_entity_by_name(self, entity_type: str, name: str) -> Optional[Entity]:
		with self.session_scope() as session:
			return (
				session.query(Entity)
				.filter(Entity.entity_type == entity_type, Entity.name == name)
				.one_or_none()
			)

	def batch_upsert_entities(self, entities: Sequence[Dict[str, Any]]) -> List[Entity]:
		if not entities:
			return []
		insert_stmt = pg_insert(Entity).values(
			[
				{
					"type": item["type"],
					"name": item["name"],
					"standardized_name": item.get("standardized_name"),
					"entity_metadata": item.get("metadata"),
				}
				for item in entities
			]
		)
		update_stmt = {
			"standardized_name": insert_stmt.excluded.standardized_name,
			"entity_metadata": insert_stmt.excluded.entity_metadata,
		}
		upsert_stmt = insert_stmt.on_conflict_do_update(
			index_elements=[Entity.entity_type, Entity.name],
			set_=update_stmt,
		).returning(Entity)

		with self.session_scope() as session:
			result = session.execute(upsert_stmt)
			return list(result.scalars().all())

	def batch_upsert_entity_document_mappings(
		self, mappings: Sequence[Dict[str, Any]]
	) -> int:
		if not mappings:
			return 0
		insert_stmt = pg_insert(EntityDocumentMapping).values(
			[
				{
					"document_id": item["document_id"],
					"entity_id": item["entity_id"],
					"confidence_score": item.get("confidence_score"),
					"mentions": item.get("mentions"),
				}
				for item in mappings
			]
		)
		update_stmt = {
			"confidence_score": insert_stmt.excluded.confidence_score,
			"mentions": insert_stmt.excluded.mentions,
		}
		upsert_stmt = insert_stmt.on_conflict_do_update(
			index_elements=[
				EntityDocumentMapping.document_id,
				EntityDocumentMapping.entity_id,
			],
			set_=update_stmt,
		)
		with self.session_scope() as session:
			result = session.execute(upsert_stmt)
			return result.rowcount or 0

	def get_entities_for_document(self, document_id: UUID) -> List[Entity]:
		document_id = self._coerce_uuid(document_id)
		with self.session_scope() as session:
			return (
				session.query(Entity)
				.join(EntityDocumentMapping)
				.filter(EntityDocumentMapping.document_id == document_id)
				.order_by(Entity.entity_id)
				.all()
			)

	# -------------------- Graph Cache --------------------
	def upsert_graph_node_cache(
		self,
		node_type: str,
		neo4j_node_id: int,
		name: Optional[str] = None,
		description: Optional[str] = None,
		properties: Optional[Dict[str, Any]] = None,
	) -> GraphNodeCache:
		insert_stmt = pg_insert(GraphNodeCache).values(
			{
				"node_type": node_type,
				"neo4j_node_id": neo4j_node_id,
				"name": name,
				"description": description,
				"properties": properties,
			}
		)
		update_stmt = {
			"node_type": insert_stmt.excluded.node_type,
			"name": insert_stmt.excluded.name,
			"description": insert_stmt.excluded.description,
			"properties": insert_stmt.excluded.properties,
		}
		upsert_stmt = insert_stmt.on_conflict_do_update(
			index_elements=[GraphNodeCache.neo4j_node_id],
			set_=update_stmt,
		).returning(GraphNodeCache)

		with self.session_scope() as session:
			result = session.execute(upsert_stmt)
			return result.scalar_one()

	def get_graph_node_cache_by_neo4j_id(self, neo4j_node_id: int) -> Optional[GraphNodeCache]:
		with self.session_scope() as session:
			return (
				session.query(GraphNodeCache)
				.filter(GraphNodeCache.neo4j_node_id == neo4j_node_id)
				.one_or_none()
			)

	def upsert_graph_edge_cache(
		self,
		neo4j_relationship_id: int,
		start_node_id: int,
		end_node_id: int,
		relationship_type: str,
		properties: Optional[Dict[str, Any]] = None,
	) -> GraphEdgeCache:
		insert_stmt = pg_insert(GraphEdgeCache).values(
			{
				"neo4j_relationship_id": neo4j_relationship_id,
				"start_node_id": start_node_id,
				"end_node_id": end_node_id,
				"relationship_type": relationship_type,
				"properties": properties,
			}
		)
		update_stmt = {
			"start_node_id": insert_stmt.excluded.start_node_id,
			"end_node_id": insert_stmt.excluded.end_node_id,
			"relationship_type": insert_stmt.excluded.relationship_type,
			"properties": insert_stmt.excluded.properties,
		}
		upsert_stmt = insert_stmt.on_conflict_do_update(
			index_elements=[GraphEdgeCache.neo4j_relationship_id],
			set_=update_stmt,
		).returning(GraphEdgeCache)

		with self.session_scope() as session:
			result = session.execute(upsert_stmt)
			return result.scalar_one()


	# -------------------- Evidence Records --------------------
	def create_evidence_record(
		self,
		document_id: UUID,
		gene_symbol: Optional[str] = None,
		variant_hgvs_c: Optional[str] = None,
		variant_hgvs_p: Optional[str] = None,
		protein_change: Optional[str] = None,
		transcript_id: Optional[str] = None,
		reference_genome: Optional[str] = None,
		disease_name: Optional[str] = None,
		icd10_code: Optional[str] = None,
		species: Optional[str] = None,
		phenotype: Optional[str] = None,
		evidence_strength: Optional[str] = None,
		evidence_classification: Optional[str] = None,
		overall_confidence: Optional[float] = None,
		is_valid: str = "false",
		acmg_levels: Optional[Dict[str, Any]] = None,
		extracted_fields: Optional[Dict[str, Any]] = None,
		ps3_evidence: Optional[Dict[str, Any]] = None,
	) -> EvidenceRecord:
		document_id = self._coerce_uuid(document_id)
		with self.session_scope() as session:
			record = EvidenceRecord(
				document_id=document_id,
				gene_symbol=gene_symbol,
				variant_hgvs_c=variant_hgvs_c,
				variant_hgvs_p=variant_hgvs_p,
				protein_change=protein_change,
				transcript_id=transcript_id,
				reference_genome=reference_genome,
				disease_name=disease_name,
				icd10_code=icd10_code,
				species=species,
				phenotype=phenotype,
				evidence_strength=evidence_strength,
				evidence_classification=evidence_classification,
				overall_confidence=overall_confidence,
				is_valid=is_valid,
				acmg_levels=acmg_levels,
				extracted_fields=extracted_fields,
				ps3_evidence=ps3_evidence,
			)
			session.add(record)
			session.flush()
			return record

	def get_evidence_by_id(self, evidence_id: int) -> Optional[EvidenceRecord]:
		with self.session_scope() as session:
			return session.get(EvidenceRecord, evidence_id)

	def search_evidence_by_gene(self, gene_symbol: str, limit: int = 50) -> List[EvidenceRecord]:
		with self.session_scope() as session:
			return (
				session.query(EvidenceRecord)
				.filter(EvidenceRecord.gene_symbol == gene_symbol)
				.order_by(EvidenceRecord.overall_confidence.desc())
				.limit(limit)
				.all()
			)

	def search_evidence_by_variant(
		self,
		variant: Optional[str] = None,
		protein_change: Optional[str] = None,
		limit: int = 50,
	) -> List[EvidenceRecord]:
		with self.session_scope() as session:
			query = session.query(EvidenceRecord)
			if variant:
				query = query.filter(
					(EvidenceRecord.variant_hgvs_c == variant)
					| (EvidenceRecord.variant_hgvs_p == variant)
				)
			if protein_change:
				query = query.filter(EvidenceRecord.protein_change == protein_change)
			return query.order_by(EvidenceRecord.overall_confidence.desc()).limit(limit).all()

	def search_evidence_multi(
		self,
		gene_symbol: Optional[str] = None,
		variant: Optional[str] = None,
		protein_change: Optional[str] = None,
		disease_name: Optional[str] = None,
		min_confidence: Optional[float] = None,
		only_valid: bool = False,
		limit: int = 100,
	) -> List[EvidenceRecord]:
		"""多条件图谱检索：基于 Variation/Gene/Protein Change 的关联证据检索"""
		with self.session_scope() as session:
			query = session.query(EvidenceRecord)
			if gene_symbol:
				query = query.filter(EvidenceRecord.gene_symbol == gene_symbol)
			if variant:
				query = query.filter(
					(EvidenceRecord.variant_hgvs_c == variant)
					| (EvidenceRecord.variant_hgvs_p == variant)
				)
			if protein_change:
				query = query.filter(EvidenceRecord.protein_change == protein_change)
			if disease_name:
				query = query.filter(EvidenceRecord.disease_name.ilike(f"%{disease_name}%"))
			if min_confidence is not None:
				query = query.filter(EvidenceRecord.overall_confidence >= min_confidence)
			if only_valid:
				query = query.filter(EvidenceRecord.is_valid == "true")
			return query.order_by(EvidenceRecord.overall_confidence.desc()).limit(limit).all()

	def get_evidence_for_document(self, document_id: UUID) -> List[EvidenceRecord]:
		document_id = self._coerce_uuid(document_id)
		with self.session_scope() as session:
			return (
				session.query(EvidenceRecord)
				.filter(EvidenceRecord.document_id == document_id)
				.order_by(EvidenceRecord.evidence_id)
				.all()
			)

	def update_evidence_record(self, evidence_id: int, **fields: Any) -> Optional[EvidenceRecord]:
		with self.session_scope() as session:
			record = session.get(EvidenceRecord, evidence_id)
			if not record:
				return None
			for key, value in fields.items():
				if hasattr(record, key):
					setattr(record, key, value)
			session.flush()
			return record


_postgres_client: Optional[PostgresClient] = None


def get_postgres_client() -> PostgresClient:
	global _postgres_client
	if _postgres_client is None:
		_postgres_client = PostgresClient()
	return _postgres_client
