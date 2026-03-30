# Phase-3 Document Parsing Implementation Plan

Mirror of `docs/plans/2026-03-06-phase-3-document-parsing.md` for reviewer tooling.

- Add lightweight `DocumentParsingAgent` and structured `DocumentParsingResult`.
- Persist raw parsing markdown/JPG artifacts immediately after parsing.
- Return additive parsing metadata in task payloads and task status API.
- Keep the existing PDF Celery workflow shape unchanged outside the parsing boundary.

## Concrete tasks

1. Add parsing result models in `src/domain/models.py`.
2. Add agent in `src/domain/agent/document_parsing.py`.
3. Add raw parsing artifact storage helper in `src/service/tasks.py`.
4. Refactor `run_node_parsing` to return structured result.
5. Refactor `process_pdf_task` to carry parsing metadata forward.
6. Extend `GET /tasks/{task_id}` additively with `parsing_metadata`.
7. Add unit tests for structured parse result and parsing persistence.

## Verification

- `uv run pytest tests/unit/test_tasks.py -k "parsing or process_pdf_task"`
- `uv run pytest tests/unit/test_tasks.py`
- `uv run pytest tests/integration/test_task_api.py`
