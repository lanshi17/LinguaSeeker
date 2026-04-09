from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

from src.services.acceptance_runner import (
    run_acceptance_set,
    sync_manifest_from_postgres,
)
from src.services.release_reporting import AcceptanceManifest


def test_sync_manifest_rows_from_postgres_updates_paper_statuses(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / 'manifest.json'
    manifest_path.write_text(
        json.dumps(
            {
                'release_no': 'v1.0',
                'locked': True,
                'expected_paper_count': 2,
                'papers': [
                    {'paper_id': 'paper-a', 'status': 'queued'},
                    {'paper_id': 'paper-b', 'status': 'queued'},
                ],
            }
        ),
        encoding='utf-8',
    )

    class FakePostgres:
        def get_acceptance_result_by_paper_id(self, paper_id: str) -> Any:
            if paper_id == 'paper-a':
                return SimpleNamespace(
                    paper_task_id='paper-1',
                    status='success',
                    error_code=None,
                    processing_duration_seconds=123.0,
                )
            return None

    manifest = sync_manifest_from_postgres(manifest_path, postgres=FakePostgres())

    assert manifest.papers[0].status == 'success'
    assert manifest.papers[0].paper_task_id == 'paper-1'
    assert manifest.papers[0].duration_seconds == 123.0


def test_run_acceptance_set_uses_real_executor_and_writes_ids() -> None:
    manifest = AcceptanceManifest.model_validate(
        {
            'release_no': 'v1.0',
            'locked': True,
            'expected_paper_count': 3,
            'papers': [
                {'paper_id': 'paper-a', 'status': 'queued'},
                {'paper_id': 'paper-b', 'status': 'queued'},
                {'paper_id': 'paper-c', 'status': 'success', 'paper_task_id': 'paper-3'},
            ],
        }
    )
    queued: List[str] = []

    def enqueuer(paper: Any) -> Dict[str, Any]:
        queued.append(paper.paper_id)
        return {
            'request_id': f"req-{paper.paper_id}",
            'paper_task_id': f"task-{paper.paper_id}",
        }

    report = run_acceptance_set(manifest, enqueue=enqueuer)

    assert report['queued_count'] == 2
    assert queued == ['paper-a', 'paper-b']
    assert manifest.papers[0].request_id == 'req-paper-a'
    assert manifest.papers[0].paper_task_id == 'task-paper-a'
