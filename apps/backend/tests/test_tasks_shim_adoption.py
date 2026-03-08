from __future__ import annotations


def test_tasks_module_uses_shimmed_imports() -> None:
    from src.api.dependencies import map_error_code as shim_map_error_code
    from src.infrastructure.minio import MinIOClient as ShimMinIOClient
    from src.infrastructure.postgres import get_postgres_client as shim_get_postgres_client
    from src.infrastructure.redis import cache_pdf_result as shim_cache_pdf_result
    from src.service import tasks as tasks_module
    from src.tools.db.qdrant_tool import QdrantManager as ShimQdrantManager
    from src.tools.db.qdrant_tool import initialize_knowledge_base as shim_initialize_knowledge_base

    assert tasks_module.MinIOClient is ShimMinIOClient
    assert tasks_module.get_postgres_client is shim_get_postgres_client
    assert tasks_module.QdrantManager is ShimQdrantManager
    assert tasks_module.initialize_knowledge_base is shim_initialize_knowledge_base
    assert tasks_module.map_error_code is shim_map_error_code
    assert tasks_module.cache_pdf_result is shim_cache_pdf_result
