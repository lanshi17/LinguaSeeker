from __future__ import annotations

import pytest

from tests.integration.e2e_live_helpers import (
    load_e2e_samples,
    poll_request_terminal,
    submit_web_batch,
)


@pytest.mark.integration
def test_submit_ten_multilingual_web_samples_reaches_terminal_state() -> None:
    samples = load_e2e_samples()

    assert [sample["sample_id"] for sample in samples] == [
        "zh-001",
        "zh-002",
        "zh-003",
        "ja-001",
        "ja-002",
        "ja-003",
        "ru-001",
        "ru-002",
        "de-001",
        "de-002",
    ]

    request_payload = submit_web_batch(samples, force_refresh=True)
    final_status = poll_request_terminal(request_payload["request_id"])

    assert final_status["status"] in {"success", "partial_failed"}
    assert len(final_status["papers"]) == 10
    assert any(paper["status"] == "success" for paper in final_status["papers"])
    assert all("paper_task_id" in paper for paper in final_status["papers"])


@pytest.mark.integration
def test_force_refresh_web_batch_does_not_collapse_to_duplicate_successes() -> None:
    request_payload = submit_web_batch(load_e2e_samples(), force_refresh=True)

    duplicate_errors = [paper for paper in request_payload["papers"] if paper.get("error_code") == "FILE_DUPLICATE"]
    queued_papers = [paper for paper in request_payload["papers"] if paper.get("status") == "queued"]

    assert len(request_payload["papers"]) == 10
    assert duplicate_errors == []
    assert len(queued_papers) == 10
    assert all(paper.get("celery_task_id") for paper in queued_papers)
