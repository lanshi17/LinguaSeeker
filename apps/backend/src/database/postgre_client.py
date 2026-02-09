from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, Iterable, List, Optional, Sequence
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
		pmid: Optional[str] = None,
		local_path: Optional[str] = None,
		status: str = "pending",
		summary: Optional[str] = None,
	) -> Document:
		with self.session_scope() as session:
			document = Document(
				title=title,
				pmid=pmid,
				local_path=local_path,
				file_hash=file_hash,
				status=status,
				summary=summary,
			)
			session.add(document)
			session.flush()
			return document

	def get_document_by_id(self, document_id: int) -> Optional[Document]:
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

	def update_document(self, document_id: int, **fields: Any) -> Optional[Document]:
		with self.session_scope() as session:
			document = session.get(Document, document_id)
			if not document:
				return None
			for key, value in fields.items():
				if hasattr(document, key):
					setattr(document, key, value)
			session.flush()
			return document

	def delete_document(self, document_id: int) -> bool:
		with self.session_scope() as session:
			document = session.get(Document, document_id)
			if not document:
				return False
			session.delete(document)
			return True

	# -------------------- Tasks --------------------
	def create_task(
		self,
		document_id: int,
		task_type: str,
		status: str = "pending",
		progress: Optional[float] = None,
		result: Optional[Dict[str, Any]] = None,
	) -> Task:
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

	def list_tasks_by_document(self, document_id: int) -> List[Task]:
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

	def get_entities_for_document(self, document_id: int) -> List[Entity]:
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


_postgres_client: Optional[PostgresClient] = None


def get_postgres_client() -> PostgresClient:
	global _postgres_client
	if _postgres_client is None:
		_postgres_client = PostgresClient()
	return _postgres_client
