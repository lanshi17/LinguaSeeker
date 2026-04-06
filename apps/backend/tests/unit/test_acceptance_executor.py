from __future__ import annotations

import pytest

from src.services.acceptance_executor import enqueue_manifest_paper
from src.services.release_reporting import AcceptancePaperRecord


def test_enqueue_manifest_paper_dispatches_web_entries() -> None:
    paper = AcceptancePaperRecord.model_validate(
        {
            "paper_id": "web-001",
            "entry_kind": "web",
            "source": "web",
            "request_payload": {"urls": ["https://example.com/paper"]},
            "status": "queued",
        }
    )
    seen: list[str] = []

    def fake_web_dispatcher(entry: AcceptancePaperRecord) -> dict[str, str]:
        seen.append(entry.paper_id)
        return {"request_id": "req-1", "paper_task_id": "paper-1"}

    result = enqueue_manifest_paper(paper, dispatchers={"web": fake_web_dispatcher})

    assert seen == ["web-001"]
    assert result == {"request_id": "req-1", "paper_task_id": "paper-1"}


def test_enqueue_manifest_paper_requires_execution_metadata() -> None:
    paper = AcceptancePaperRecord.model_validate(
        {
            "paper_id": "api-001",
            "entry_kind": "api",
            "status": "queued",
        }
    )

    with pytest.raises(ValueError, match="request_payload"):
        enqueue_manifest_paper(paper, dispatchers={"api": lambda _: {}})
