from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import httpx
import psycopg2
from src.infrastructure.neo4j import get_neo4j_client
from src.infrastructure.postgres import _build_conninfo

API_BASE = os.getenv("ACMG_E2E_API_BASE_URL", "http://127.0.0.1:8000/api/v1")
SAMPLES_PATH = Path(__file__).resolve().parents[1] / "data" / "e2e_multilingual_web_samples.json"
TERMINAL_STATES = {"success", "failed", "partial_failed"}


def load_e2e_samples() -> list[dict[str, str]]:
    return json.loads(SAMPLES_PATH.read_text(encoding="utf-8"))


def _client() -> httpx.Client:
    return httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0))


def submit_web_batch(samples: list[dict[str, str]], force_refresh: bool) -> dict[str, Any]:
    payload = {
        "task_form": json.dumps(
            {
                "goal": "PS3/BS3 evidence",
                "disease": "hereditary disease variant interpretation",
                "country": "MULTI",
                "language": "MULTI",
            },
            ensure_ascii=False,
        ),
        "urls": [sample["url"] for sample in samples],
        "source": "web",
        "force_refresh": force_refresh,
    }
    with _client() as client:
        response = client.post(f"{API_BASE}/tasks/requests/web/crawl", json=payload)
        response.raise_for_status()
        return response.json()


def get_request_status(request_id: str) -> dict[str, Any]:
    with _client() as client:
        response = client.get(f"{API_BASE}/tasks/requests/{request_id}")
        response.raise_for_status()
        return response.json()


def get_paper_detail(paper_task_id: str) -> dict[str, Any]:
    with _client() as client:
        response = client.get(f"{API_BASE}/tasks/papers/{paper_task_id}")
        response.raise_for_status()
        return response.json()


def get_document_bundle(document_id: str) -> dict[str, Any]:
    with _client() as client:
        response = client.get(f"{API_BASE}/evidence/document/{document_id}")
        response.raise_for_status()
        return response.json()["data"]


def query_request_persistence(request_id: str) -> dict[str, int]:
    sql = {
        "task_requests": "SELECT count(*) FROM task_requests WHERE request_id = %s::uuid",
        "paper_tasks": "SELECT count(*) FROM paper_tasks WHERE request_id = %s::uuid",
        "successful_papers": "SELECT count(*) FROM paper_tasks WHERE request_id = %s::uuid AND status = 'success'",
        "documents": """
            SELECT count(DISTINCT pt.document_id)
            FROM paper_tasks pt
            WHERE pt.request_id = %s::uuid AND pt.document_id IS NOT NULL
        """,
        "sentence_alignments": """
            SELECT count(*)
            FROM sentence_alignments sa
            JOIN paper_tasks pt ON pt.paper_task_id = sa.paper_task_id
            WHERE pt.request_id = %s::uuid
        """,
        "evidence_records": """
            SELECT count(*)
            FROM evidence_records er
            JOIN paper_tasks pt ON pt.document_id = er.document_id
            WHERE pt.request_id = %s::uuid
        """,
        "kg_events": """
            SELECT count(*)
            FROM kg_events
            WHERE request_id = %s::uuid AND event_type = 'paper_completed'
        """,
    }

    result: dict[str, int] = {}
    with psycopg2.connect(_build_conninfo()) as conn:
        with conn.cursor() as cur:
            for key, statement in sql.items():
                cur.execute(statement, (request_id,))
                result[key] = int(cur.fetchone()[0])
    return result


def pick_graph_query(bundle: dict[str, Any]) -> dict[str, str]:
    records = bundle.get("graph", {}).get("evidence_records", [])
    for record in records:
        gene_symbol = str(record.get("gene_symbol") or "").strip()
        if gene_symbol:
            return {"gene_symbol": gene_symbol}
        variant = str(record.get("variant_hgvs_c") or record.get("variant_hgvs_p") or "").strip()
        if variant:
            return {"variant": variant}
    raise AssertionError("Unable to derive graph query from document bundle")


def search_graph(query: dict[str, str]) -> dict[str, Any]:
    with _client() as client:
        response = client.post(f"{API_BASE}/evidence/search", json=query)
        response.raise_for_status()
        return response.json()["data"]


def resync_document(document_id: str) -> dict[str, Any]:
    with _client() as client:
        response = client.post(f"{API_BASE}/evidence/sync/document/{document_id}")
        response.raise_for_status()
        return response.json()["data"]


def neo4j_document_projection(document_id: str) -> dict[str, int]:
    neo = get_neo4j_client()
    rows = neo.run_query(
        """
        MATCH (doc:Document {document_id: $document_id})
        OPTIONAL MATCH (e:Evidence)-[r:FROM_DOCUMENT]->(doc)
        RETURN count(DISTINCT doc) AS document_nodes,
               count(DISTINCT r) AS from_document_edges
        """,
        {"document_id": document_id},
    )
    row = rows[0] if rows else {}
    return {
        "document_nodes": int(row.get("document_nodes", 0) or 0),
        "from_document_edges": int(row.get("from_document_edges", 0) or 0),
    }


def poll_request_terminal(
    request_id: str,
    timeout_seconds: int = 1800,
    interval_seconds: int = 5,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        payload = get_request_status(request_id)
        papers = payload.get("papers", [])
        if papers and all(str(paper.get("status", "")).lower() in TERMINAL_STATES for paper in papers):
            return payload
        time.sleep(interval_seconds)
    raise AssertionError(
        f"Request {request_id} did not reach a terminal state within {timeout_seconds}s"
    )
