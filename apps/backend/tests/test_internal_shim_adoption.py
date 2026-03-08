from __future__ import annotations

from pathlib import Path


def test_main_uses_api_and_infrastructure_shims() -> None:
    import main as root_main
    from src.api.routes.core import router as core_router
    from src.api.routes.evidence import router as evidence_router
    from src.api.routes.task import router as task_router
    from src.infrastructure.minio import MinIOClient

    assert root_main.api_routers is core_router
    assert root_main.task_api_routers is task_router
    assert root_main.evidence_api_routers is evidence_router
    assert root_main.MinIOClient is MinIOClient


def test_celery_uses_services_shim() -> None:
    from src.celery_app import celery_app

    includes = tuple(celery_app.conf.include or ())
    assert "src.services.task_manager" in includes


def test_presentation_api_uses_shims() -> None:
    import src.presentation.api as presentation_api
    from src.infrastructure.minio import MinIOClient
    from src.infrastructure.postgres import get_postgres_client
    from src.services.task_manager import process_pdf_task

    assert presentation_api.MinIOClient is MinIOClient
    assert presentation_api.get_postgres_client is get_postgres_client
    assert presentation_api.process_pdf_task is process_pdf_task


def test_presentation_api_source_imports_shims() -> None:
    source = (Path(__file__).resolve().parents[1] / "src/presentation/api.py").read_text()

    assert "from src.infrastructure.redis import (" in source
    assert "from src.infrastructure.postgres import get_postgres_client" in source
    assert "from src.services.task_manager import process_pdf_task" in source
    assert "from src.infrastructure.minio import MinIOClient" in source
    assert "from src.api.dependencies import build_log_link, contract_http_exception" in source


def test_presentation_task_api_uses_shims() -> None:
    import src.presentation.task_api as task_api
    from src.api.dependencies import contract_http_exception
    from src.infrastructure.minio import MinIOClient
    from src.infrastructure.postgres import get_postgres_client
    from src.services.task_manager import process_pdf_task
    from src.services.task_manager import process_pubmed_paper_task, process_web_page_task

    assert task_api.MinIOClient is MinIOClient
    assert task_api.get_postgres_client is get_postgres_client
    assert task_api.process_pdf_task is process_pdf_task
    assert task_api.process_pubmed_paper_task is process_pubmed_paper_task
    assert task_api.process_web_page_task is process_web_page_task
    assert task_api.contract_http_exception is contract_http_exception


def test_presentation_task_api_source_imports_shims() -> None:
    source = (Path(__file__).resolve().parents[1] / "src/presentation/task_api.py").read_text()
    normalized = " ".join(source.split())

    assert "from src.infrastructure.minio import MinIOClient" in source
    assert "from src.infrastructure.postgres import get_postgres_client" in source
    assert "from src.infrastructure.redis import list_celery_task_meta" in source
    assert "from src.api.dependencies import contract_http_exception" in source
    assert "from src.services.task_manager import" in normalized
    assert "process_pdf_task" in normalized
    assert "process_pubmed_paper_task" in normalized
    assert "process_web_page_task" in normalized


def test_presentation_graph_api_uses_infrastructure_shim() -> None:
    import src.presentation.graph_api as graph_api
    from src.infrastructure.neo4j import get_neo4j_client

    assert graph_api.get_neo4j_client is get_neo4j_client
