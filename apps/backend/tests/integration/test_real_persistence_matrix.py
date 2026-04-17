from __future__ import annotations

import pytest

from tests.integration.e2e_live_helpers import (
    get_document_bundle,
    get_paper_detail,
    load_e2e_samples,
    query_request_persistence,
    submit_web_batch,
)


@pytest.mark.integration
def test_document_evidence_endpoint_returns_source_target_and_ps3_for_successful_samples() -> None:
    request_payload = submit_web_batch(load_e2e_samples(), force_refresh=True)

    for paper in request_payload["papers"]:
        if paper["status"] != "queued":
            continue
        detail = get_paper_detail(paper["paper_task_id"])
        bundle = get_document_bundle(detail["document_id"])

        assert bundle["source_text"].strip()
        assert bundle["translated_text"].strip()
        assert isinstance(bundle["ps3_evidence"], dict)
        assert isinstance(bundle["graph"], dict)
        assert bundle["graph"]["document_id"] == detail["document_id"]


@pytest.mark.integration
def test_postgres_persistence_matrix_contains_request_document_alignment_evidence_and_kg_rows() -> None:
    request_payload = submit_web_batch(load_e2e_samples(), force_refresh=True)
    persistence = query_request_persistence(request_payload["request_id"])

    assert persistence["task_requests"] == 1
    assert persistence["paper_tasks"] == 10
    assert persistence["documents"] == 10
    assert persistence["successful_papers"] == 0
    assert persistence["sentence_alignments"] == 0
    assert persistence["evidence_records"] > 0
    assert persistence["kg_events"] == 0
