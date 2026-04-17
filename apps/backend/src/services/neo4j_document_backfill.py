from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.infrastructure.neo4j import Neo4jClient, get_neo4j_client
from src.infrastructure.postgres import PostgresClient, get_postgres_client


def _document_props(document: Any) -> Dict[str, Any]:
    props: Dict[str, Any] = {}
    for field in ('title', 'file_hash', 'status', 'pmid'):
        value = getattr(document, field, None)
        if value:
            props[field] = value
    return props


def run_document_metadata_backfill(
    *,
    limit: int,
    offset: int = 0,
    postgres_client: Optional[PostgresClient] = None,
    neo4j_client: Optional[Neo4jClient] = None,
) -> Dict[str, Any]:
    postgres = postgres_client or get_postgres_client()
    neo = neo4j_client or get_neo4j_client()
    documents = postgres.list_documents(limit=max(int(limit), 0), offset=max(int(offset), 0))

    document_ids: List[str] = []
    for document in documents:
        document_id = str(document.document_id)
        neo.upsert_document(document_id, **_document_props(document))
        document_ids.append(document_id)

    return {
        'processed': len(document_ids),
        'document_ids': document_ids,
    }
