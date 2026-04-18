from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import text

from src.infrastructure.neo4j import Neo4jClient, get_neo4j_client
from src.infrastructure.postgres import PostgresClient, get_postgres_client


def _list_disease_rows(postgres: Any, *, limit: int, offset: int) -> List[Dict[str, str]]:
    if isinstance(postgres, PostgresClient):
        with postgres.session_scope() as session:
            rows = session.execute(
                text(
                    """
                    SELECT DISTINCT disease_name, icd10_code
                    FROM evidence_records
                    WHERE disease_name IS NOT NULL
                      AND icd10_code IS NOT NULL
                    ORDER BY disease_name
                    OFFSET :offset LIMIT :limit
                    """
                ),
                {"offset": max(int(offset), 0), "limit": max(int(limit), 0)},
            ).fetchall()
        return [
            {"disease_name": row.disease_name, "icd10_code": row.icd10_code}
            for row in rows
        ]
    explicit = getattr(postgres, 'list_distinct_disease_icd10_pairs', None)
    if callable(explicit):
        return list(explicit(limit=limit, offset=offset))
    raise TypeError('Unsupported postgres client for disease ICD10 backfill')


def run_disease_icd10_backfill(
    *,
    limit: int,
    offset: int = 0,
    postgres_client: Optional[PostgresClient] = None,
    neo4j_client: Optional[Neo4jClient] = None,
) -> Dict[str, Any]:
    postgres = postgres_client or get_postgres_client()
    neo = neo4j_client or get_neo4j_client()
    rows = _list_disease_rows(postgres, limit=limit, offset=offset)

    diseases: List[str] = []
    for row in rows:
        disease_name = str(row.get('disease_name') or '').strip()
        icd10_code = str(row.get('icd10_code') or '').strip()
        if not disease_name or not icd10_code:
            continue
        neo.upsert_disease(disease_name, icd10_code=icd10_code)
        diseases.append(disease_name)

    return {'processed': len(diseases), 'diseases': diseases}
