from __future__ import annotations

import json
from datetime import datetime, timezone
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


def test_sync_manifest_rows_from_postgres_uses_latest_attempt_window_when_duration_missing(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / 'manifest.json'
    manifest_path.write_text(
        json.dumps(
            {
                'release_no': 'v1.0',
                'locked': True,
                'expected_paper_count': 1,
                'papers': [
                    {'paper_id': 'paper-a', 'paper_task_id': 'task-1', 'status': 'queued'},
                ],
            }
        ),
        encoding='utf-8',
    )

    class FakePostgres:
        def get_acceptance_result_by_paper_id(self, paper_id: str) -> Any:
            return None

        def get_paper_task(self, paper_task_id: str) -> Any:
            assert paper_task_id == 'task-1'
            return SimpleNamespace(
                paper_task_id='task-1',
                status='failed',
                error_code='TRANSLATION_FAILED',
                processing_duration_seconds=None,
                created_at=datetime(2026, 4, 7, 9, 21, 15, tzinfo=timezone.utc),
                updated_at=datetime(2026, 4, 9, 3, 20, 20, tzinfo=timezone.utc),
            )

        def get_latest_paper_task_log(self, paper_task_id: str, *, node: str | None = None) -> Any:
            assert paper_task_id == 'task-1'
            if node == 'pipeline':
                return SimpleNamespace(
                    created_at=datetime(2026, 4, 9, 3, 13, 37, tzinfo=timezone.utc),
                    node='pipeline',
                )
            if node is None:
                return SimpleNamespace(
                    created_at=datetime(2026, 4, 9, 3, 20, 20, tzinfo=timezone.utc),
                    node='ops_reconcile',
                )
            if node == 'translation':
                return SimpleNamespace(
                    created_at=datetime(2026, 4, 9, 3, 20, 20, tzinfo=timezone.utc),
                    node='translation',
                )
            return None

    manifest = sync_manifest_from_postgres(manifest_path, postgres=FakePostgres())

    assert manifest.papers[0].status == 'failed'
    assert manifest.papers[0].duration_seconds == 403.0
    assert manifest.papers[0].worker_started_at == '2026-04-09T03:13:37+00:00'
    assert manifest.papers[0].completed_at == '2026-04-09T03:20:20+00:00'


def test_sync_manifest_from_postgres_removes_pre_execution_note_after_terminal_run(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / 'manifest.json'
    manifest_path.write_text(
        json.dumps(
            {
                'release_no': 'v1.0',
                'locked': True,
                'expected_paper_count': 1,
                'notes': [
                    'Manifest is populated and locked, but the acceptance run has not been executed yet.'
                ],
                'papers': [
                    {'paper_id': 'paper-a', 'paper_task_id': 'task-1', 'status': 'queued'}
                ],
            }
        ),
        encoding='utf-8',
    )

    class FakePostgres:
        def get_acceptance_result_by_paper_id(self, paper_id: str) -> Any:
            return SimpleNamespace(
                paper_task_id='task-1',
                status='success',
                error_code=None,
                processing_duration_seconds=123.0,
            )

    manifest = sync_manifest_from_postgres(manifest_path, postgres=FakePostgres(), write=True)

    assert (
        'Manifest is populated and locked, but the acceptance run has not been executed yet.'
        not in manifest.notes
    )
    assert any(
        note.startswith('Acceptance run reached terminal state:')
        for note in manifest.notes
    )



def test_sync_manifest_from_postgres_normalizes_terminal_notes_without_db_lookup(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / 'manifest.json'
    manifest_path.write_text(
        json.dumps(
            {
                'release_no': 'v1.0',
                'locked': True,
                'expected_paper_count': 1,
                'notes': [
                    'Manifest is populated and locked, but the acceptance run has not been executed yet.'
                ],
                'papers': [
                    {
                        'paper_id': 'paper-a',
                        'paper_task_id': 'task-1',
                        'status': 'success',
                        'duration_seconds': 123.0,
                    }
                ],
            }
        ),
        encoding='utf-8',
    )

    class ExplodingPostgres:
        def get_acceptance_result_by_paper_id(self, paper_id: str) -> Any:
            raise AssertionError('db lookup should not happen for terminal manifest rows')

        def get_paper_task(self, paper_task_id: str) -> Any:
            raise AssertionError('db lookup should not happen for terminal manifest rows')

    manifest = sync_manifest_from_postgres(
        manifest_path,
        postgres=ExplodingPostgres(),
        write=True,
    )

    assert (
        'Manifest is populated and locked, but the acceptance run has not been executed yet.'
        not in manifest.notes
    )
    assert any(
        note.startswith('Acceptance run reached terminal state:')
        for note in manifest.notes
    )



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
