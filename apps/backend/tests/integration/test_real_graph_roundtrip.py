from __future__ import annotations

import pytest

from tests.integration.e2e_live_helpers import (
    get_document_bundle,
    load_e2e_samples,
    neo4j_document_projection,
    pick_graph_query,
    resync_document,
    search_graph,
    submit_web_batch,
)


@pytest.mark.integration
def test_graph_api_returns_backend_nodes_edges_for_documents_with_evidence() -> None:
    request_payload = submit_web_batch(load_e2e_samples(), force_refresh=True)

    evidence_docs = []
    for paper in request_payload["papers"]:
        bundle = get_document_bundle(paper["document_id"])
        if (bundle.get("graph") or {}).get("total_evidence", 0) > 0:
            evidence_docs.append((paper, bundle))

    assert evidence_docs

    successful_roundtrips = 0
    for paper, bundle in evidence_docs:
        query = pick_graph_query(bundle)
        graph_payload = search_graph(query)

        if (
            graph_payload.get("nodes")
            and graph_payload.get("edges")
            and graph_payload.get("document_count", 0) >= 1
            and any(
                str(item.get("document_id")) == str(paper["document_id"])
                for item in graph_payload.get("evidence_records", [])
            )
        ):
            successful_roundtrips += 1

    assert successful_roundtrips >= 1


@pytest.mark.integration
def test_resync_document_preserves_neo4j_document_and_evidence_links() -> None:
    request_payload = submit_web_batch(load_e2e_samples(), force_refresh=True)

    first_with_evidence = None
    for paper in request_payload["papers"]:
        bundle = get_document_bundle(paper["document_id"])
        if (bundle.get("graph") or {}).get("total_evidence", 0) > 0:
            first_with_evidence = paper
            break

    assert first_with_evidence is not None

    resync_payload = resync_document(first_with_evidence["document_id"])
    projection = neo4j_document_projection(first_with_evidence["document_id"])

    assert resync_payload["synced"] >= 1
    assert projection["document_nodes"] == 1
    assert projection["from_document_edges"] >= 1
