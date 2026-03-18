from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional, Sequence, Union
from uuid import UUID

import psycopg2
from loguru import logger
from sqlalchemy import create_engine, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, joinedload, sessionmaker

from src.config import app_config as cfg
from src.infrastructure.models import (
    Base,
    ClinGenEvidenceProfile,
    ClinVarVariation,
    Document,
    Entity,
    EntityDocumentMapping,
    EvidenceRecord,
    GraphEdgeCache,
    GraphNodeCache,
    PaperTask,
    PaperTaskLog,
    SentenceAlignment,
    Task,
    TaskLog,
    TaskRequest,
    User,
    VariationCitation,
)


def _build_database_url(db_name: Optional[str] = None) -> str:
    url = URL.create(
        drivername="postgresql+psycopg2",
        username=cfg.postgresql.user,
        password=cfg.postgresql.password or "",
        host=cfg.postgresql.host,
        port=cfg.postgresql.port,
        database=db_name or cfg.postgresql.database,
    )
    return url.render_as_string(hide_password=False)


def get_database_url(db_name: Optional[str] = None) -> str:
    return _build_database_url(db_name)


def _build_conninfo(db_name: Optional[str] = None) -> str:
    return (
        f"host={cfg.postgresql.host} "
        f"port={cfg.postgresql.port} "
        f"dbname={db_name or cfg.postgresql.database} "
        f"user={cfg.postgresql.user} "
        f"password={cfg.postgresql.password}"
    )


def ensure_database_exists(db_name: Optional[str] = None) -> None:
    target_db = db_name or cfg.postgresql.database
    conninfo = _build_conninfo("postgres")
    try:
        with psycopg2.connect(conninfo) as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s", (target_db,)
                )
                exists = cur.fetchone()
                if not exists:
                    cur.execute(f'CREATE DATABASE "{target_db}"')
                    logger.info("Created PostgreSQL database: {}", target_db)
    except Exception as exc:
        logger.warning("Failed to ensure database exists: {}", exc)
        raise


def initialize_schema(
    db_name: Optional[str] = None, schema_name: Optional[str] = None
) -> None:
    ensure_database_exists(db_name)
    engine = get_engine(db_name)
    if schema_name:
        engine = engine.execution_options(schema_translate_map={None: schema_name})
    Base.metadata.create_all(engine)


def _derive_request_status(
    *,
    total_count: int,
    duplicate_count: int,
    success_count: int,
    success_non_duplicate_count: int,
    failed_count: int,
    running_count: int,
    queued_count: int,
) -> str:
    if total_count <= 0:
        return "failed"
    if running_count > 0:
        return "running"
    if queued_count > 0:
        return "queued"
    if failed_count > 0 and success_count > 0:
        return "partial_failed"
    if failed_count > 0:
        return "failed"
    if duplicate_count == total_count:
        return "success"
    if success_count == total_count:
        return "success"
    if success_non_duplicate_count > 0 or duplicate_count > 0:
        return "success"
    return "queued"


def get_engine(db_name: Optional[str] = None):
    conninfo = _build_conninfo(db_name)
    return create_engine(
        "postgresql+psycopg2://",
        creator=lambda: psycopg2.connect(conninfo),
        pool_size=cfg.postgresql.pool_size,
        max_overflow=cfg.postgresql.max_overflow,
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
    def _coerce_uuid(value: Union[UUID, str, int]) -> UUID:
        if isinstance(value, UUID):
            return value
        if isinstance(value, int):
            if value < 0:
                raise ValueError("UUID integer value must be non-negative")
            return UUID(int=value)
        text = str(value).strip()
        try:
            return UUID(text)
        except ValueError as exc:
            if text.isdigit():
                return UUID(int=int(text))
            raise ValueError(f"Invalid UUID value: {value}") from exc

    @contextmanager
    def session_scope(self) -> Iterator[Session]:
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
            return (
                query.order_by(Document.document_id).offset(offset).limit(limit).all()
            )

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

    def delete_paper_task(self, paper_task_id: Union[UUID, str]) -> bool:
        paper_uuid = self._coerce_uuid(paper_task_id)
        with self.session_scope() as session:
            paper_task = session.get(PaperTask, paper_uuid)
            if not paper_task:
                return False
            session.delete(paper_task)
            return True

    # -------------------- Tasks --------------------
    def create_task(
        self,
        document_id: UUID,
        task_type: str,
        status: str = "pending",
        workflow_status: str = "PENDING",
        processing_steps: Optional[Dict[str, Any]] = None,
        progress: Optional[float] = None,
        file_size_bytes: Optional[int] = None,
        processing_duration_seconds: Optional[float] = None,
        result: Optional[Dict[str, Any]] = None,
        error_details: Optional[Dict[str, Any]] = None,
    ) -> Task:
        document_id = self._coerce_uuid(document_id)
        with self.session_scope() as session:
            task = Task(
                document_id=document_id,
                task_type=task_type,
                status=status,
                workflow_status=workflow_status,
                processing_steps=processing_steps,
                progress=progress,
                file_size_bytes=file_size_bytes,
                processing_duration_seconds=processing_duration_seconds,
                result=result,
                error_details=error_details,
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

    def append_task_log(
        self,
        document_id: UUID,
        status: str,
        category: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        missing_fields_detail: Optional[Dict[str, Any]] = None,
        task_id: Optional[int] = None,
    ) -> TaskLog:
        document_id = self._coerce_uuid(document_id)
        with self.session_scope() as session:
            entry = TaskLog(
                document_id=document_id,
                task_id=task_id,
                status=status,
                category=category,
                payload=payload,
                missing_fields_detail=missing_fields_detail,
            )
            session.add(entry)
            session.flush()
            return entry

    # -------------------- Task Requests / Paper Tasks (M0/M1) --------------------
    def create_task_request(
        self,
        task_form_text: str,
        status: str = "queued",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TaskRequest:
        with self.session_scope() as session:
            entry = TaskRequest(
                task_form_text=task_form_text,
                status=status,
                request_metadata=metadata,
            )
            session.add(entry)
            session.flush()
            return entry

    def get_task_request(self, request_id: Union[UUID, str]) -> Optional[TaskRequest]:
        request_uuid = self._coerce_uuid(request_id)
        with self.session_scope() as session:
            return session.get(TaskRequest, request_uuid)

    def update_task_request(
        self, request_id: Union[UUID, str], **fields: Any
    ) -> Optional[TaskRequest]:
        request_uuid = self._coerce_uuid(request_id)
        with self.session_scope() as session:
            entry = session.get(TaskRequest, request_uuid)
            if not entry:
                return None
            for key, value in fields.items():
                if key == "metadata":
                    setattr(entry, "request_metadata", value)
                elif hasattr(entry, key):
                    setattr(entry, key, value)
            session.flush()
            return entry

    def create_paper_task(
        self,
        request_id: Union[UUID, str],
        status: str = "queued",
        workflow_status: str = "PENDING",
        document_id: Optional[Union[UUID, str]] = None,
        original_filename: Optional[str] = None,
        file_hash: Optional[str] = None,
        processing_steps: Optional[Dict[str, Any]] = None,
        file_size_bytes: Optional[int] = None,
        processing_duration_seconds: Optional[float] = None,
        error_code: Optional[str] = None,
        error_details: Optional[Dict[str, Any]] = None,
        duplicate_of: Optional[Union[UUID, str]] = None,
        celery_task_id: Optional[str] = None,
        fulltext_unavailable: str = "false",
        warning_codes: Optional[List[str]] = None,
        node_trace: Optional[Dict[str, Any]] = None,
    ) -> PaperTask:
        request_uuid = self._coerce_uuid(request_id)
        document_uuid = (
            self._coerce_uuid(document_id) if document_id is not None else None
        )
        duplicate_uuid = (
            self._coerce_uuid(duplicate_of) if duplicate_of is not None else None
        )
        with self.session_scope() as session:
            entry = PaperTask(
                request_id=request_uuid,
                document_id=document_uuid,
                original_filename=original_filename,
                file_hash=file_hash,
                status=status,
                workflow_status=workflow_status,
                processing_steps=processing_steps,
                file_size_bytes=file_size_bytes,
                processing_duration_seconds=processing_duration_seconds,
                error_code=error_code,
                error_details=error_details,
                duplicate_of=duplicate_uuid,
                celery_task_id=celery_task_id,
                fulltext_unavailable=fulltext_unavailable,
                warning_codes=warning_codes,
                node_trace=node_trace,
            )
            session.add(entry)
            session.flush()
            return entry

    def get_paper_task(self, paper_task_id: Union[UUID, str]) -> Optional[PaperTask]:
        paper_uuid = self._coerce_uuid(paper_task_id)
        with self.session_scope() as session:
            return session.get(PaperTask, paper_uuid)

    def get_paper_task_by_celery_task_id(
        self, celery_task_id: str
    ) -> Optional[PaperTask]:
        if not celery_task_id:
            return None
        with self.session_scope() as session:
            return (
                session.query(PaperTask)
                .filter(PaperTask.celery_task_id == celery_task_id)
                .order_by(PaperTask.created_at.desc())
                .first()
            )

    def list_paper_tasks_by_request(
        self, request_id: Union[UUID, str]
    ) -> List[PaperTask]:
        request_uuid = self._coerce_uuid(request_id)
        with self.session_scope() as session:
            return (
                session.query(PaperTask)
                .filter(PaperTask.request_id == request_uuid)
                .order_by(PaperTask.created_at.asc())
                .all()
            )

    def update_paper_task(
        self, paper_task_id: Union[UUID, str], **fields: Any
    ) -> Optional[PaperTask]:
        paper_uuid = self._coerce_uuid(paper_task_id)
        with self.session_scope() as session:
            entry = session.get(PaperTask, paper_uuid)
            if not entry:
                return None
            for key, value in fields.items():
                if hasattr(entry, key):
                    setattr(entry, key, value)
            session.flush()
            return entry

    def append_paper_task_log(
        self,
        paper_task_id: Union[UUID, str],
        status: str,
        node: Optional[str] = None,
        error_code: Optional[str] = None,
        message: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> PaperTaskLog:
        paper_uuid = self._coerce_uuid(paper_task_id)
        with self.session_scope() as session:
            entry = PaperTaskLog(
                paper_task_id=paper_uuid,
                status=status,
                node=node,
                error_code=error_code,
                message=message,
                payload=payload,
            )
            session.add(entry)
            session.flush()
            return entry

    def get_latest_paper_task_log(
        self,
        paper_task_id: Union[UUID, str],
        *,
        node: Optional[str] = None,
    ) -> Optional[PaperTaskLog]:
        paper_uuid = self._coerce_uuid(paper_task_id)
        with self.session_scope() as session:
            query = session.query(PaperTaskLog).filter(
                PaperTaskLog.paper_task_id == paper_uuid
            )
            if node is not None:
                query = query.filter(PaperTaskLog.node == node)
            return query.order_by(PaperTaskLog.created_at.desc()).first()

    def create_sentence_alignment(
        self,
        paper_task_id: Union[UUID, str],
        source_sentence: str,
        en_sentence: str,
        source_start: Optional[int] = None,
        source_end: Optional[int] = None,
        en_start: Optional[int] = None,
        en_end: Optional[int] = None,
    ) -> SentenceAlignment:
        paper_uuid = self._coerce_uuid(paper_task_id)
        with self.session_scope() as session:
            entry = SentenceAlignment(
                paper_task_id=paper_uuid,
                source_sentence=source_sentence,
                en_sentence=en_sentence,
                source_start=source_start,
                source_end=source_end,
                en_start=en_start,
                en_end=en_end,
            )
            session.add(entry)
            session.flush()
            return entry

    def find_latest_paper_task_by_hash(self, file_hash: str) -> Optional[PaperTask]:
        with self.session_scope() as session:
            return (
                session.query(PaperTask)
                .filter(PaperTask.file_hash == file_hash)
                .order_by(PaperTask.created_at.desc())
                .first()
            )

    def refresh_task_request_status(
        self, request_id: Union[UUID, str]
    ) -> Optional[TaskRequest]:
        request_uuid = self._coerce_uuid(request_id)
        with self.session_scope() as session:
            entry = session.get(TaskRequest, request_uuid)
            if not entry:
                return None
            papers: List[PaperTask] = (
                session.query(PaperTask)
                .filter(PaperTask.request_id == request_uuid)
                .order_by(PaperTask.created_at.asc())
                .all()
            )
            if not papers:
                entry.status = "failed"
                session.flush()
                return entry

            statuses = [str(p.status) for p in papers]
            success_count = sum(1 for s in statuses if s == "success")
            duplicate_count = sum(
                1
                for p in papers
                if str(p.status) == "success"
                and str(p.error_code or "") == "FILE_DUPLICATE"
            )
            failed_count = sum(1 for s in statuses if s == "failed")
            running_count = sum(1 for s in statuses if s == "running")
            queued_count = sum(1 for s in statuses if s == "queued")

            entry.status = _derive_request_status(
                total_count=len(papers),
                duplicate_count=duplicate_count,
                success_count=success_count,
                success_non_duplicate_count=(success_count - duplicate_count),
                failed_count=failed_count,
                running_count=running_count,
                queued_count=queued_count,
            )

            session.flush()
            return entry

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

    def get_graph_node_cache_by_neo4j_id(
        self, neo4j_node_id: int
    ) -> Optional[GraphNodeCache]:
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

    # -------------------- ClinVar / ClinGen Variations --------------------
    def get_clinvar_variation(self, variation_id: int) -> Optional[ClinVarVariation]:
        with self.session_scope() as session:
            return session.get(ClinVarVariation, variation_id)

    def get_clinvar_variation_by_hgvs(self, hgvs: str) -> Optional[ClinVarVariation]:
        if not hgvs:
            return None
        with self.session_scope() as session:
            return (
                session.query(ClinVarVariation)
                .filter(func.lower(ClinVarVariation.primary_hgvs) == hgvs.lower())
                .one_or_none()
            )

    def upsert_clinvar_variation(
        self, variation_id: int, **fields: Any
    ) -> ClinVarVariation:
        with self.session_scope() as session:
            variation = session.get(ClinVarVariation, variation_id)
            if not variation:
                variation = ClinVarVariation(variation_id=variation_id)
                session.add(variation)
            for key, value in fields.items():
                if hasattr(variation, key) and value is not None:
                    setattr(variation, key, value)
            session.flush()
            return variation

    def list_variation_citations(self, variation_id: int) -> List[VariationCitation]:
        with self.session_scope() as session:
            return (
                session.query(VariationCitation)
                .options(joinedload(VariationCitation.document))
                .filter(VariationCitation.variation_id == variation_id)
                .order_by(VariationCitation.citation_id)
                .all()
            )

    def replace_variation_citations(
        self,
        variation_id: int,
        source: str,
        entries: Sequence[Dict[str, Any]],
    ) -> None:
        with self.session_scope() as session:
            session.query(VariationCitation).filter(
                VariationCitation.variation_id == variation_id,
                VariationCitation.source == source,
            ).delete(synchronize_session=False)

            for entry in entries:
                citation = VariationCitation(
                    variation_id=variation_id,
                    source=source,
                    pmid=entry.get("pmid"),
                    document_id=entry.get("document_id"),
                    evidence_strength=entry.get("evidence_strength"),
                    notes=entry.get("notes"),
                    citation_metadata=entry.get("metadata"),
                )
                session.add(citation)

    def upsert_internal_variation_citation(
        self,
        variation_id: int,
        document_id: UUID,
        evidence_strength: Optional[str] = None,
        pmid: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> VariationCitation:
        document_id = self._coerce_uuid(document_id)
        with self.session_scope() as session:
            citation = (
                session.query(VariationCitation)
                .filter(
                    VariationCitation.variation_id == variation_id,
                    VariationCitation.source == "internal",
                    VariationCitation.document_id == document_id,
                )
                .one_or_none()
            )
            if not citation:
                citation = VariationCitation(
                    variation_id=variation_id,
                    source="internal",
                    document_id=document_id,
                    pmid=pmid,
                    evidence_strength=evidence_strength,
                    citation_metadata=metadata,
                )
                session.add(citation)
            else:
                if pmid:
                    citation.pmid = pmid
                if evidence_strength:
                    citation.evidence_strength = evidence_strength
                if metadata:
                    citation.citation_metadata = metadata
            session.flush()
            return citation

    def list_clingen_profiles(self, variation_id: int) -> List[ClinGenEvidenceProfile]:
        with self.session_scope() as session:
            return (
                session.query(ClinGenEvidenceProfile)
                .filter(ClinGenEvidenceProfile.variation_id == variation_id)
                .order_by(ClinGenEvidenceProfile.published_at.desc().nullslast())
                .all()
            )

    def replace_clingen_profiles(
        self, variation_id: int, profiles: Sequence[Dict[str, Any]]
    ) -> None:
        with self.session_scope() as session:
            session.query(ClinGenEvidenceProfile).filter(
                ClinGenEvidenceProfile.variation_id == variation_id
            ).delete(synchronize_session=False)
            for payload in profiles:
                profile = ClinGenEvidenceProfile(
                    variation_id=variation_id,
                    assertion_id=payload["assertion_id"],
                    disease_label=payload.get("disease_label"),
                    disease_mondo=payload.get("disease_mondo"),
                    expert_panel=payload.get("expert_panel"),
                    classification=payload.get("classification"),
                    published_at=payload.get("published_at"),
                    guideline_label=payload.get("guideline_label"),
                    evidence_codes=payload.get("evidence_codes"),
                    score_breakdown=payload.get("score_breakdown"),
                    raw_payload=payload.get("raw_payload"),
                )
                session.add(profile)

    # -------------------- Evidence Records --------------------
    def create_evidence_record(
        self,
        document_id: UUID,
        gene_symbol: Optional[str] = None,
        variant_hgvs_c: Optional[str] = None,
        variant_hgvs_p: Optional[str] = None,
        protein_change: Optional[str] = None,
        clinvar_variation_id: Optional[int] = None,
        transcript_id: Optional[str] = None,
        reference_genome: Optional[str] = None,
        disease_name: Optional[str] = None,
        icd10_code: Optional[str] = None,
        species: Optional[str] = None,
        phenotype: Optional[str] = None,
        evidence_strength: Optional[str] = None,
        evidence_classification: Optional[str] = None,
        overall_confidence: Optional[float] = None,
        arbitration_score: Optional[float] = None,
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
                clinvar_variation_id=clinvar_variation_id,
                transcript_id=transcript_id,
                reference_genome=reference_genome,
                disease_name=disease_name,
                icd10_code=icd10_code,
                species=species,
                phenotype=phenotype,
                evidence_strength=evidence_strength,
                evidence_classification=evidence_classification,
                overall_confidence=overall_confidence,
                arbitration_score=arbitration_score,
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

    def search_evidence_by_gene(
        self, gene_symbol: str, limit: int = 50
    ) -> List[EvidenceRecord]:
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
        clinvar_variation_id: Optional[int] = None,
        limit: int = 50,
    ) -> List[EvidenceRecord]:
        with self.session_scope() as session:
            query = session.query(EvidenceRecord)
            if clinvar_variation_id is not None:
                query = query.filter(
                    EvidenceRecord.clinvar_variation_id == clinvar_variation_id
                )
            if variant:
                query = query.filter(
                    (EvidenceRecord.variant_hgvs_c == variant)
                    | (EvidenceRecord.variant_hgvs_p == variant)
                )
            if protein_change:
                query = query.filter(EvidenceRecord.protein_change == protein_change)
            return (
                query.order_by(EvidenceRecord.overall_confidence.desc())
                .limit(limit)
                .all()
            )

    def search_evidence_multi(
        self,
        gene_symbol: Optional[str] = None,
        variant: Optional[str] = None,
        protein_change: Optional[str] = None,
        clinvar_variation_id: Optional[int] = None,
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
            if clinvar_variation_id is not None:
                query = query.filter(
                    EvidenceRecord.clinvar_variation_id == clinvar_variation_id
                )
            if protein_change:
                query = query.filter(EvidenceRecord.protein_change == protein_change)
            if disease_name:
                query = query.filter(
                    EvidenceRecord.disease_name.ilike(f"%{disease_name}%")
                )
            if min_confidence is not None:
                query = query.filter(
                    EvidenceRecord.overall_confidence >= min_confidence
                )
            if only_valid:
                query = query.filter(EvidenceRecord.is_valid == "true")
            return (
                query.order_by(EvidenceRecord.overall_confidence.desc())
                .limit(limit)
                .all()
            )

    def get_evidence_for_document(self, document_id: UUID) -> List[EvidenceRecord]:
        document_id = self._coerce_uuid(document_id)
        with self.session_scope() as session:
            return (
                session.query(EvidenceRecord)
                .filter(EvidenceRecord.document_id == document_id)
                .order_by(EvidenceRecord.evidence_id)
                .all()
            )

    def update_evidence_record(
        self, evidence_id: int, **fields: Any
    ) -> Optional[EvidenceRecord]:
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
_schema_initialized: bool = False


def _ensure_schema_initialized() -> None:
    global _schema_initialized
    if _schema_initialized:
        return
    try:
        initialize_schema()
        _schema_initialized = True
        logger.info("PostgreSQL schema initialization ensured via SQLAlchemy metadata")
    except Exception as exc:
        logger.warning("Failed to auto-initialize PostgreSQL schema: {}", exc)
        raise


def get_postgres_client() -> PostgresClient:
    global _postgres_client
    if _postgres_client is None:
        _ensure_schema_initialized()
        _postgres_client = PostgresClient()
    return _postgres_client
