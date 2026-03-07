from __future__ import annotations


def test_infrastructure_reexports_legacy_clients() -> None:
    from src.database.minio_client import MinIOClient as LegacyMinIOClient
    from src.database.neo4j_client import Neo4jClient as LegacyNeo4jClient
    from src.database.neo4j_client import get_neo4j_client as legacy_get_neo4j_client
    from src.database.postgre_client import PostgresClient as LegacyPostgresClient
    from src.database.postgre_client import get_postgres_client as legacy_get_postgres_client
    from src.database.qdrant_client import QdrantManager as LegacyQdrantManager
    from src.database.qdrant_client import get_qdrant_manager as legacy_get_qdrant_manager
    from src.database.redis_client import RedisClient as LegacyRedisClient
    from src.infrastructure.minio import MinIOClient
    from src.infrastructure.neo4j import Neo4jClient, get_neo4j_client
    from src.infrastructure.postgres import PostgresClient, get_postgres_client
    from src.infrastructure.qdrant import QdrantManager, get_qdrant_manager
    from src.infrastructure.redis import RedisClient

    assert PostgresClient is LegacyPostgresClient
    assert get_postgres_client is legacy_get_postgres_client
    assert Neo4jClient is LegacyNeo4jClient
    assert get_neo4j_client is legacy_get_neo4j_client
    assert QdrantManager is LegacyQdrantManager
    assert get_qdrant_manager is legacy_get_qdrant_manager
    assert MinIOClient is LegacyMinIOClient
    assert RedisClient is LegacyRedisClient


def test_services_task_manager_reexports_legacy_tasks() -> None:
    from src.service.tasks import init_knowledge_base_if_needed as legacy_init_knowledge_base
    from src.service.tasks import process_pdf_task as legacy_process_pdf_task
    from src.service.tasks import process_pubmed_paper_task as legacy_process_pubmed_paper_task
    from src.service.tasks import process_web_page_task as legacy_process_web_page_task
    from src.services.task_manager import init_knowledge_base_if_needed
    from src.services.task_manager import process_pdf_task
    from src.services.task_manager import process_pubmed_paper_task
    from src.services.task_manager import process_web_page_task

    assert init_knowledge_base_if_needed is legacy_init_knowledge_base
    assert process_pdf_task is legacy_process_pdf_task
    assert process_pubmed_paper_task is legacy_process_pubmed_paper_task
    assert process_web_page_task is legacy_process_web_page_task


def test_api_route_shims_reexport_legacy_routers() -> None:
    from src.api.routes.core import router as core_router
    from src.api.routes.evidence import router as evidence_router
    from src.api.routes.task import router as task_router
    from src.presentation.api import router as legacy_core_router
    from src.presentation.graph_api import router as legacy_evidence_router
    from src.presentation.task_api import router as legacy_task_router

    assert core_router is legacy_core_router
    assert evidence_router is legacy_evidence_router
    assert task_router is legacy_task_router


def test_api_dependencies_reexports_error_contract_helpers() -> None:
    from src.api.dependencies import build_log_link, contract_http_exception, failed_payload
    from src.presentation.error_contract import build_log_link as legacy_build_log_link
    from src.presentation.error_contract import (
        contract_http_exception as legacy_contract_http_exception,
    )
    from src.presentation.error_contract import failed_payload as legacy_failed_payload

    assert build_log_link is legacy_build_log_link
    assert contract_http_exception is legacy_contract_http_exception
    assert failed_payload is legacy_failed_payload
