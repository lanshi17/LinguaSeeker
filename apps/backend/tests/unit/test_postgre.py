from __future__ import annotations

from typing import Generator
from uuid import uuid4

import psycopg2
import pytest
from sqlalchemy.exc import IntegrityError, OperationalError
from loguru import logger

from src.config import settings as cfg
from src.database.postgre_client import (
    Base,
    PostgresClient,
    _derive_request_status,
    _build_database_url,
    _build_conninfo,
    ensure_database_exists,
    get_engine,
    get_postgres_client,
    initialize_schema,
)


def _postgres_conninfo(db_name: str) -> str:
    return _build_conninfo(db_name)


@pytest.fixture(scope="session")
def postgres_available() -> Generator[None, None, None]:
    try:
        with psycopg2.connect(_postgres_conninfo("postgres")) as conn:
            conn.autocommit = True
        yield
    except Exception:
        pytest.skip("PostgreSQL is not available for tests")


@pytest.fixture(scope="session")
def test_db_name(postgres_available) -> Generator[str, None, None]:
    yield cfg.postgres_db


@pytest.fixture(scope="function")
def test_engine(test_db_name: str):
    engine = None
    schema_name = None
    try:
        schema_name = _create_test_schema(test_db_name)
        engine = get_engine(test_db_name).execution_options(
            schema_translate_map={None: schema_name}
        )
        logger.info(
            "PostgreSQL test connect host={} port={} db={} user={}",
            cfg.postgres_host,
            cfg.postgres_port,
            test_db_name,
            cfg.postgres_user,
        )
        logger.info(
            "PostgreSQL config host={} db={} user={}",
            cfg.postgres_host,
            cfg.postgres_db,
            cfg.postgres_user,
        )
        Base.metadata.create_all(engine)
    except (OperationalError, psycopg2.Error):
        logger.exception("PostgreSQL test database setup failed")
        if schema_name:
            try:
                _drop_test_schema(test_db_name, schema_name)
            except (OperationalError, psycopg2.Error):
                logger.exception("PostgreSQL cleanup schema failed")
        if engine:
            engine.dispose()
        pytest.skip("PostgreSQL schema setup failed for test database")
    yield engine
    if schema_name:
        try:
            _drop_test_schema(test_db_name, schema_name)
        except (OperationalError, psycopg2.Error):
            logger.exception("PostgreSQL cleanup schema failed")
    if engine:
        engine.dispose()


def _log_password_diagnostics() -> None:
    password = cfg.postgres_password or ""
    has_special = any(not char.isalnum() for char in password)
    logger.info(
        "PostgreSQL password length={} has_special_char={}",
        len(password),
        has_special,
    )


def _create_test_schema(db_name: str) -> str:
    schema_name = f"test_{uuid4().hex[:8]}"
    with psycopg2.connect(_postgres_conninfo(db_name)) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(f'CREATE SCHEMA "{schema_name}"')
    return schema_name


def _drop_test_schema(db_name: str, schema_name: str) -> None:
    with psycopg2.connect(_postgres_conninfo(db_name)) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE')


@pytest.mark.unit
def test_postgres_connection(postgres_available) -> None:
    try:
        _log_password_diagnostics()
        with psycopg2.connect(_postgres_conninfo(cfg.postgres_db)) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                result = cur.fetchone()
                assert result[0] == 1
    except Exception as e:
        pytest.fail(f"PostgreSQL connection test failed: {e}")


@pytest.mark.unit
def test_build_database_url() -> None:
    url_default = _build_database_url()
    assert f"/{cfg.postgres_db}" in url_default
    custom_name = f"acmg_test_{uuid4().hex[:6]}"
    url_custom = _build_database_url(custom_name)
    assert f"/{custom_name}" in url_custom


@pytest.mark.unit
def test_direct_connection() -> None:
    conn = psycopg2.connect(
        host=cfg.postgres_host,
        port=cfg.postgres_port,
        database=cfg.postgres_db,
        user=cfg.postgres_user,
        password=cfg.postgres_password,
    )
    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version()")
            assert cur.fetchone()


def test_schema_helpers(postgres_available) -> None:
    schema_name = None
    try:
        _log_password_diagnostics()
        schema_name = _create_test_schema(cfg.postgres_db)
        logger.info(
            "PostgreSQL schema connect host={} port={} db={} user={}",
            cfg.postgres_host,
            cfg.postgres_port,
            cfg.postgres_db,
            cfg.postgres_user,
        )
        initialize_schema(cfg.postgres_db, schema_name=schema_name)
        with psycopg2.connect(_postgres_conninfo(cfg.postgres_db)) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT to_regclass(%s)", (f"{schema_name}.users",))
                assert cur.fetchone()[0] == f"{schema_name}.users"
                cur.execute("SELECT to_regclass(%s)", (f"{schema_name}.documents",))
                assert cur.fetchone()[0] == f"{schema_name}.documents"
    except (OperationalError, psycopg2.Error):
        logger.exception("PostgreSQL schema auth failed")
        pytest.skip("PostgreSQL authentication failed for test schema")
    finally:
        if schema_name:
            try:
                _drop_test_schema(cfg.postgres_db, schema_name)
            except (OperationalError, psycopg2.Error):
                logger.exception("PostgreSQL cleanup schema failed")


@pytest.mark.unit
def test_user_crud(test_engine) -> None:
    client = PostgresClient(engine=test_engine)
    user = client.create_user("alice", "alice@example.com")
    assert user.id is not None
    assert client.get_user_by_id(user.id).username == "alice"
    assert client.get_user_by_username("alice").email == "alice@example.com"


def test_document_crud_and_hash(test_engine) -> None:
    client = PostgresClient(engine=test_engine)
    doc = client.create_document(
        title="doc",
        pmid="pmid-1",
        local_path="path",
        file_hash="hash-1",
        status="uploaded",
        summary="summary",
    )
    assert client.get_document_by_id(doc.document_id).title == "doc"
    assert client.get_document_by_pmid("pmid-1").document_id == doc.document_id
    assert client.find_document_by_hash("hash-1").document_id == doc.document_id
    assert len(client.list_documents(status="uploaded")) == 1
    updated = client.update_document(doc.document_id, status="done")
    assert updated.status == "done"
    assert client.delete_document(doc.document_id) is True


def test_document_hash_unique_constraint(test_engine) -> None:
    client = PostgresClient(engine=test_engine)
    client.create_document(
        title="doc-1",
        pmid=None,
        local_path=None,
        file_hash="dup-hash",
    )
    with pytest.raises(IntegrityError):
        client.create_document(
            title="doc-2",
            pmid=None,
            local_path=None,
            file_hash="dup-hash",
        )


def test_task_crud(test_engine) -> None:
    client = PostgresClient(engine=test_engine)
    doc = client.create_document(
        title="doc",
        pmid=None,
        local_path=None,
        file_hash="hash-task",
    )
    task = client.create_task(doc.document_id, task_type="parse", status="queued")
    assert client.get_task_by_id(task.task_id).task_type == "parse"
    assert len(client.list_tasks_by_document(doc.document_id)) == 1
    updated = client.update_task(task.task_id, status="done", progress=1.0)
    assert updated.status == "done"
    assert client.delete_task(task.task_id) is True


def test_entity_crud_and_batch_upsert(test_engine) -> None:
    client = PostgresClient(engine=test_engine)
    entity = client.create_entity("gene", "BRCA1", standardized_name="BRCA1")
    assert client.get_entity_by_id(entity.entity_id).name == "BRCA1"
    assert client.get_entity_by_name("gene", "BRCA1").entity_id == entity.entity_id

    upserted = client.batch_upsert_entities(
        [
            {"type": "gene", "name": "TP53", "standardized_name": "TP53"},
            {"type": "gene", "name": "BRCA1", "standardized_name": "BRCA1-v2"},
        ]
    )
    assert len(upserted) == 2
    assert client.get_entity_by_name("gene", "BRCA1").standardized_name == "BRCA1-v2"


def test_entity_document_mapping_and_query(test_engine) -> None:
    client = PostgresClient(engine=test_engine)
    doc = client.create_document(
        title="doc",
        pmid=None,
        local_path=None,
        file_hash="hash-map",
    )
    entity = client.create_entity("disease", "cancer")
    inserted = client.batch_upsert_entity_document_mappings(
        [
            {
                "document_id": doc.document_id,
                "entity_id": entity.entity_id,
                "confidence_score": 0.9,
                "mentions": {"count": 2},
            }
        ]
    )
    assert inserted == 1
    entities = client.get_entities_for_document(doc.document_id)
    assert [item.entity_id for item in entities] == [entity.entity_id]


def test_graph_cache_upserts(test_engine) -> None:
    client = PostgresClient(engine=test_engine)
    node = client.upsert_graph_node_cache(
        node_type="gene",
        neo4j_node_id=101,
        name="BRCA1",
        description="desc",
        properties={"a": 1},
    )
    assert node.neo4j_node_id == 101
    fetched = client.get_graph_node_cache_by_neo4j_id(101)
    assert fetched.name == "BRCA1"

    edge = client.upsert_graph_edge_cache(
        neo4j_relationship_id=201,
        start_node_id=101,
        end_node_id=102,
        relationship_type="ASSOCIATED",
        properties={"p": "v"},
    )
    assert edge.neo4j_relationship_id == 201


def test_get_postgres_client_singleton() -> None:
    client_a = get_postgres_client()
    client_b = get_postgres_client()
    assert client_a is client_b


@pytest.mark.parametrize(
    ("counts", "expected_status"),
    [
        (
            {
                "total_count": 2,
                "duplicate_count": 2,
                "success_count": 2,
                "success_non_duplicate_count": 0,
                "failed_count": 0,
                "running_count": 0,
                "queued_count": 0,
            },
            "success",
        ),
        (
            {
                "total_count": 2,
                "duplicate_count": 1,
                "success_count": 1,
                "success_non_duplicate_count": 0,
                "failed_count": 1,
                "running_count": 0,
                "queued_count": 0,
            },
            "partial_failed",
        ),
        (
            {
                "total_count": 3,
                "duplicate_count": 1,
                "success_count": 3,
                "success_non_duplicate_count": 2,
                "failed_count": 0,
                "running_count": 0,
                "queued_count": 0,
            },
            "success",
        ),
    ],
)
def test_derive_request_status_duplicate_semantics(
    counts: dict[str, int], expected_status: str
) -> None:
    assert _derive_request_status(**counts) == expected_status
