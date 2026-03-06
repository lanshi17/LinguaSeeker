# Phase-3 Document Parsing Implementation Plan

## Decision

- Chosen approach: add a lightweight `DocumentParsingAgent` plus a structured `DocumentParsingResult`.
- Why: it centralizes MinerU parsing, raw markdown/image collection, parsing artifact persistence, and parser metadata without rewriting the whole PDF workflow.
- Deferred: broad parser-provider abstraction, new DB tables, and a dedicated parsing API endpoint.

## Scope

- Add a domain-level parsing agent that wraps MinerU parsing and raw asset collection.
- Persist raw parsing artifacts to MinIO immediately after parsing succeeds.
- Propagate parsing metadata into the existing Celery payload and task status surface.
- Keep the existing PDF workflow shape (`acquisition -> parsing -> translation -> extraction -> acmg`).

## Files To Change

- `src/domain/models.py`
  - add `DocumentParsingArtifact` and `DocumentParsingResult`
- `src/domain/agent/document_parsing.py`
  - add `DocumentParsingAgent`
- `src/domain/mineru/component.py`
  - optionally expose callback/progress metadata through `MinerUResponse`
- `src/service/tasks.py`
  - integrate `DocumentParsingAgent`
  - add parsing artifact storage helper
  - carry parsing metadata into `PipelineResult` and task payload
- `src/service/dtos.py`
  - add optional parsing metadata to task status response if needed
- `src/presentation/task_api.py`
  - expose additive parsing metadata in `GET /tasks/{task_id}`
- `tests/unit/test_tasks.py`
  - add failing tests for parse-result persistence and payload propagation

## Implementation Steps

1. Add `DocumentParsingResult` model carrying:
   - `markdown_content`
   - `image_paths`
   - `mineru_folder`
   - `parser_backend`
   - `parser_task_id`
   - `warnings`

2. Add `DocumentParsingAgent` that:
   - validates parse inputs
   - calls `MinerUComponent.minerU_pipeline`
   - falls back to existing PaddleOCR stub behavior
   - collects `full.md` and `.jpg` artifacts
   - returns a structured `DocumentParsingResult`

3. Add raw parsing artifact persistence helper in `src/service/tasks.py`:
   - upload parsed markdown to processed-results bucket
   - upload extracted JPGs to processed-results bucket
   - return object keys / URLs for task payloads and logs

4. Refactor `run_node_parsing` to:
   - use `DocumentParsingAgent`
   - return `DocumentParsingResult` instead of a tuple
   - enrich node logs with parser backend, MinerU task id, image count, and raw artifact keys

5. Refactor `process_pdf_task` to:
   - consume `DocumentParsingResult`
   - use `result.markdown_content` and `result.image_paths` downstream
   - persist `mineru_folder` and parsing metadata into the returned payload
   - preserve additive compatibility for existing callers

6. Extend task status API to expose parsing metadata additively:
   - `parsing_metadata`: backend, mineru task id, image count, mineru folder, raw asset keys

## TDD Order

1. `tests/unit/test_tasks.py::test_run_node_parsing_returns_structured_result`
2. `tests/unit/test_tasks.py::test_process_pdf_task_persists_parsing_metadata`
3. `tests/unit/test_tasks.py::test_process_pdf_task_parsing_artifacts_saved_before_extraction`

## Verification

- `uv run pytest tests/unit/test_tasks.py -k "parsing or process_pdf_task"`
- `uv run pytest tests/unit/test_tasks.py`
- `uv run pytest tests/integration/test_task_api.py`
- LSP diagnostics on modified files
