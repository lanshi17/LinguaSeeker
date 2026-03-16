# ACMG PS3/BS3 Workflow Optimization (Microservices + Status Migration)

## TL;DR
> **Summary**: Split the current monolith Celery pipeline into dedicated parsing/translation/extraction microservices (Celery as the cross-service bus), migrate backend `workflow_status` values to the user-facing state machine, and persist MinerU parsing outputs (sanitized response + parsing manifest) to Postgres without storing any URLs.
> **Deliverables**:
> - Parsing/translation/extraction microservices (each: Celery worker + minimal FastAPI health/metrics)
> - Versioned Celery task names + explicit queue routing per microservice
> - `workflow_status` migration to new enum values (keeping existing `processing_steps`)
> - Postgres persistence for MinerU `mineru_response_sanitized` + `parsing_manifest` (hybrid spill policy)
> - API response URL generation from MinIO object_keys (no URLs stored in Postgres)
> - Observability baseline (Prometheus metrics endpoints + correlation IDs)
> - Contract/idempotency/integration tests using existing infra compose
> **Effort**: XL
> **Parallel**: YES — 4 waves
> **Critical Path**: Contracts/queues → DB + status migration → parsing microservice → translation microservice → extraction microservice → supervisor/orchestrator cutover → tests/observability

## Context
### Original Request
- End-to-end “优化计划” for ACMG PS3/BS3 workflow with Celery orchestration, node status to frontend, and explicit requirement: “mineru返回数据保存的文件和目录, 将mineru的返回的响应json存入pgsql”.

### Interview Summary (decisions locked)
- Microservice delivery: **一次性全拆** now (parsing / translation / extraction as separate microservices).
- Cross-service bus: **Celery** (each microservice runs a worker + minimal FastAPI for health/metrics).
- MinerU persistence: store **sanitized final MinerU response + executor-generated parsing manifest** as JSONB on **existing `paper_tasks`**; **do NOT store any URLs** (upload/presigned/api paths).
- Parsing manifest size: **Hybrid threshold**
  - If `image_count <= 200`: store `image_object_keys` inline in JSONB
  - If `image_count > 200`: store only `images_prefix + image_count + image_keys_manifest_object_key + sha256` and put full list JSON into MinIO
- Workflow status alignment: **migrate backend `workflow_status` values** to the user-facing state machine, while **keeping existing `processing_steps`** as fine-grained progress.
- Provenance: **轻量溯源** only (MinIO object_keys + key params + timing/status/error codes + DB IDs; no full LLM prompt/response bodies).
- API URL policy: **server-generate URLs** at response time from stored object_keys; Postgres/logs store object_keys only.

### Metis Review (gaps addressed)
- Resolved via plan defaults (no further user decisions needed):
  - Use **Alembic** for DB schema changes (already present in `apps/backend/database/alembic/*`) even though runtime also uses `Base.metadata.create_all()`.
  - Define strict DTO envelopes + schema_version for Celery payloads.
  - Define compatibility strategy for API/workflow status migration (dual-read/dual-write window).

### Oracle Review (guardrails incorporated)
- Use versioned, fully-qualified task names (`parsing.parse_document.v1`) and dedicated queues per microservice.
- Postgres is canonical for progress; Celery is at-least-once → design idempotency.
- Enforce strict Pydantic validation + schema_version envelope.
- Avoid storing sensitive payloads in Redis result backend (`ignore_result=True`).

## Work Objectives
### Core Objective
Implement a microservice-based PS3/BS3 pipeline (parsing/translation/extraction) with durable, user-facing workflow statuses and full provenance via Postgres + MinIO object keys, while eliminating URL persistence and hardening correctness (idempotency/retries/timeouts).

### Deliverables
1) **New workflow_status values** (user state machine) applied across DB rows, enums, API responses, and supervisor graph.
2) **New Postgres columns** on `paper_tasks` for MinerU parsing persistence:
   - `mineru_response_sanitized` JSONB
   - `parsing_manifest` JSONB (hybrid spill)
3) **Microservices**
   - `parsing-service`: consumes MinIO upload object_key(s), runs MinerU/PaddleOCR fallback, uploads artifacts, writes `mineru_response_sanitized` + `parsing_manifest`
   - `translation-service`: consumes markdown object_key, outputs English markdown object_key
   - `extraction-service`: consumes English markdown + images, outputs evidence JSON object_key
4) **Celery contract + routing**
   - versioned task names + per-service queues + explicit routing
5) **API compatibility**
   - continue to serve `get_task_status` and websocket stream with new workflow_status; URLs derived from object_keys
6) **Observability baseline**
   - `/metrics` endpoints + correlation IDs
7) **Tests**
   - contract tests for DTO envelopes
   - idempotency tests
   - state migration tests
   - integration test using `apps/backend/database/podman-compose.yml`

### Definition of Done (agent-verifiable)
- `pytest` passes locally for backend test suite (including updated status transition tests).
- New columns exist and are populated after parsing stage.
- No Postgres JSON persisted fields contain any of:
  - `http://` or `https://`
  - `/results/` API paths
  - MinerU upstream URL fields (`download_url`, `full_zip_url`, `file_urls`)
- `apps/backend/.work_logs.sh` is confirmed git-ignored and must never be committed; any secrets found there must be rotated outside this repo.
- Workflow status stored in `paper_tasks.workflow_status` uses ONLY the new user-facing values.
- Microservice Celery workers can process a sample PDF end-to-end using only IDs + object_keys in Celery messages.
- `/api/v1/task/{id}` (or existing status endpoint) returns URLs (derived) without storing them.

### Must Have
- Strictly versioned DTO envelopes for cross-service Celery tasks.
- Idempotent stage execution (at-least-once safe).
- Preserve existing `processing_steps` and progress percentage logic.

### Must NOT Have (guardrails)
- Must NOT store presigned URLs, MinIO direct URLs, or API-path URLs in Postgres JSON.
- Must NOT put document text, images, or LLM prompts/responses into Redis result backend.
- Must NOT rely on Celery result backend for user-facing progress.

## Verification Strategy
> ZERO HUMAN INTERVENTION — all verification is agent-executed.
- Test decision: **tests-after** (existing pytest suite; add/adjust tests alongside changes)
- QA policy: every task below includes agent-executed QA scenarios (Bash only; no frontend/Playwright coverage assumed in this repo).
- Evidence artifacts: executor stores logs/screenshots under `.sisyphus/evidence/task-{N}-{slug}.{ext}`

## Execution Strategy
### Parallel Execution Waves
Wave 1 (Foundations / contracts / migrations)
- Task routing + DTO contract package
- WorkflowStatus migration design + dual-read compatibility
- DB migrations for new columns

Wave 2 (Microservices scaffolding)
- Parsing microservice (MinerU + persistence + idempotency)
- Translation microservice
- Extraction microservice

Wave 3 (Orchestrator + supervisor cutover)
- Update supervisor/orchestrator to call microservice tasks
- Fix extraction→adjudication coupling
- URL generation policy in API responses

Wave 4 (Observability + hardening + integration tests)
- Prometheus metrics
- Integration/contract/idempotency tests
- Retry/timeout tuning + Redis visibility_timeout

### Dependency Matrix (high level)
- DTO contracts + queues (Wave 1) block all microservices.
- DB columns (Wave 1) block parsing microservice persistence.
- Parsing microservice blocks translation/extraction downstream.
- Orchestrator cutover blocks E2E integration tests.

## TODOs

> NOTE: All file paths are under `apps/backend/` unless otherwise stated.

- [ ] 0. Plan-wide invariants (contracts, idempotency, no-URL persistence)

  **What to do**:
   - Enforce: Celery payloads are IDs + MinIO object_keys only (never markdown text/images).
   - Enforce: Postgres is canonical for workflow/progress; Celery result backend is not used for UX.
   - Enforce: “no URLs in Postgres” (no `http(s)://`, no `/results/` paths, no MinerU upstream URL fields).
   - Enforce at-least-once safety: every stage task must be idempotent (deterministic output keys + safe re-run).
   - Enforce concurrency rule: At most ONE active stage task mutates a given `paper_task_id` at a time (or else JSONB `processing_steps` read-modify-write will lose updates; current `PostgresClient.update_paper_task()` has no CAS/locking).

  **Recommended Agent Profile**:
  - Category: `unspecified-high`
  - Skills: [`verification-before-completion`]

  **Parallelization**: Can Parallel: N/A (applies to all tasks)

  **References**:
  - Current URL-producing helpers: `src/services/task_manager.py::_store_parsing_artifacts_in_minio`, `_store_outputs_in_minio`
  - MinIO key builders: `src/infrastructure/minio.py` (object_key builders)

  **Acceptance Criteria**:
  - [ ] All later tasks include explicit checks for URL-free persistence and idempotency.

  **QA Scenarios**:
  ```
  Scenario: URL persistence guard
    Tool: Bash
    Steps: Add a shared helper in tests that asserts serialized JSON has no URL substrings
    Expected: Used by parsing/translation/extraction tests
    Evidence: .sisyphus/evidence/task-0-guard.txt
  ```

- [ ] 1. Define new workflow_status enum + compatibility mapping

  **What to do**:
  1) Replace OLD `WorkflowStatus` values in `src/services/enum.py` with the new user-facing state machine values:
     - `PENDING`, `DOWNLOADING`, `PARSING`, `TRANSLATING`, `EXTRACTING`, `CLASSIFYING`, `ADJUDICATING`, `SUCCESS`, `FAILURE`
     - Keep names UPPERCASE to match existing style.
  2) Update/replace:
     - `WORKFLOW_STATUS_TRANSITIONS`
     - `STEP_TO_WORKFLOW_STATUS` mapping so steps map to new coarse statuses.
  3) Decide how `processing_steps` steps map:
     - acquisition step → `DOWNLOADING`
     - parsing step → `PARSING`
     - translation step → `TRANSLATING`
     - extraction step → `EXTRACTING`
     - reasoning/classification step → `CLASSIFYING`
     - adjudication step → `ADJUDICATING`
  4) Add a **compatibility shim** function (same module) that can coerce old persisted values to new ones for a transition window (for reading existing rows), then plan a one-time DB backfill.

  **Must NOT do**:
  - Do not rename `processing_steps` step keys; keep step keys stable.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: cross-cutting enums + tests.
  - Skills: [`systematic-debugging`] — to handle transition test fallout.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 2,3,7 | Blocked By: —

  **References**:
  - Enum definitions: `src/services/enum.py`
  - Tests: `tests/test_state_transitions.py`
  - Supervisor literals: `src/agents/supervisor.py` (currently uses lowercase "completed"/"failed")

  **Acceptance Criteria**:
  - [ ] `pytest apps/backend/tests/test_state_transitions.py -q` passes after updates.

  **QA Scenarios**:
  ```
  Scenario: Derive workflow status from processing_steps
    Tool: Bash
    Steps:
      1) Run: pytest tests/test_state_transitions.py::test_derive_workflow_status_* -q
    Expected: PASS
    Evidence: .sisyphus/evidence/task-1-workflow-status.txt

  Scenario: Coerce old persisted values
    Tool: Bash
    Steps:
      1) Add/Run unit tests that feed old values like PROCESSING_PDF into coercion fn
    Expected: PASS (mapped to PARSING)
    Evidence: .sisyphus/evidence/task-1-coerce-old.txt
  ```

- [ ] 2. Add Alembic migration for `paper_tasks` MinerU persistence columns

  **What to do**:
  1) Create new Alembic revision under `database/alembic/versions/` to add to `paper_tasks`:
     - `mineru_response_sanitized` JSONB NULL
     - `parsing_manifest` JSONB NULL
     - Add indexed scalar columns (REQUIRED):
       - `parser_backend` String(50) NULL
       - `parser_task_id` String(100) NULL
       - `mineru_folder` Text NULL  (debug-only local path; NOT a URL; may be omitted from API responses)
     - Create indexes:
       - `ix_paper_tasks_parser_backend`
       - `ix_paper_tasks_parser_task_id`
  2) Update SQLAlchemy model `PaperTask` in `src/infrastructure/models.py` to include these new columns.
  3) Decide migration toolchain policy:
     - Use Alembic for prod/dev DB migrations.
     - Keep `Base.metadata.create_all()` for local bootstrap but ensure it includes new columns.

  **Must NOT do**:
  - Do not store URL fields in these columns.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: DB schema + migration correctness.
  - Skills: [`systematic-debugging`] — migration/test interplay.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 4 | Blocked By: —

  **References**:
  - Models: `src/infrastructure/models.py` (PaperTask around lines ~393+)
  - Alembic config: `database/alembic.ini`, `database/alembic/env.py`
  - Prior migration pattern: `database/alembic/versions/20260306_01_task_status_workflow_fields.py`

  **Acceptance Criteria**:
  - [ ] Running Alembic upgrade (command used in repo) applies new columns.
  - [ ] SQLAlchemy model reflects new columns.

  **QA Scenarios**:
  ```
  Scenario: Migration applies cleanly
    Tool: Bash
    Steps:
      1) Start infra via podman-compose (or docker-compose equivalent)
      2) Run alembic upgrade head
    Expected: DB has new columns on paper_tasks
    Evidence: .sisyphus/evidence/task-2-alembic.txt

  Scenario: Local bootstrap still works
    Tool: Bash
    Steps:
      1) Run a short script that calls initialize_schema() against empty DB
    Expected: Tables created with new columns
    Evidence: .sisyphus/evidence/task-2-create-all.txt
  ```

- [ ] 3. Define cross-service Celery DTO envelopes + task name/queue conventions

   **What to do**:
   1) Create a shared “contracts” module/package inside backend repo at `src/contracts/`:
      - Pydantic DTOs with `schema_version`.
      - Task name constants and queue names.
   2) Define versioned Celery task names:
      - `parsing.parse_document.v1`
      - `translation.translate_markdown.v1`
      - `extraction.extract_evidence.v1`
   3) Define dedicated queues (names are FINAL; no alternatives):
      - `q.parsing`, `q.translation`, `q.extraction`, plus existing `retry`.
   4) Update `src/celery_app.py` to register queues + routes for these tasks, and set broker transport options:
      - `broker_transport_options = {"visibility_timeout": cfg.task_timeout_seconds + 600}` (MUST be > hard time limit)
      - Add `task_default_queue = "default"` unchanged.
   5) For all stage tasks, set Celery options:
      - `ignore_result=True`
      - `acks_late=True`
      - `task_reject_on_worker_lost=True`
      - `soft_time_limit = cfg.node_<stage>_timeout_seconds`
      - `time_limit = cfg.node_<stage>_timeout_seconds + 60` (cleanup grace)
   6) Enforce JSON-only serialization (already configured) and explicitly forbid pickle/yaml.

  **Must NOT do**:
  - Do not pass large payloads (markdown text, images) through Celery messages.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: cross-service interface design.
  - Skills: [`test-driven-development`] — contract tests first.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 4,5,6 | Blocked By: —

  **References**:
  - Existing Celery app: `src/celery_app.py`
  - Existing task naming: `src/services/task_manager.py` (`@celery_app.task(name="tasks.process_pdf")`)

  **Acceptance Criteria**:
  - [ ] Contract DTOs validate golden payload fixtures.
  - [ ] Celery routes contain explicit mapping for new task names.

  **QA Scenarios**:
  ```
  Scenario: DTO schema validation
    Tool: Bash
    Steps:
      1) Run pytest tests/contracts/test_parsing_dto.py -q
    Expected: PASS
    Evidence: .sisyphus/evidence/task-3-contract-dto.txt

  Scenario: Celery route config
    Tool: Bash
    Steps:
      1) Run a unit test that imports celery_app and asserts task_routes entries exist
    Expected: PASS
    Evidence: .sisyphus/evidence/task-3-celery-routes.txt
  ```

- [ ] 4. Implement parsing microservice worker (MinerU + persistence)

  **What to do**:
  1) Create a new service module (in-repo) `src/microservices/parsing/` with:
     - Celery task handler for `parsing.parse_document.v1`
     - Minimal FastAPI app for `/healthz` and `/metrics`
  2) Input to task: `{paper_task_id, document_id, upload_bucket, upload_object_key, idempotency_key, schema_version}`.
  3) Implement idempotency:
     - Deterministic MinIO keys for outputs under `{document_id}/parsing/...`.
     - If outputs already exist (`minio.file_exists`), short-circuit success and just ensure DB fields are populated.
  4) Run MinerU parse (existing agent `DocumentParsingAgent`) and upload artifacts via existing MinIO client.
   5) Persist to Postgres on `paper_tasks`:
      - `mineru_response_sanitized` (allowlist fields; exclude URLs) with this exact JSON shape:
        ```json
        {
          "schema_version": 1,
          "parser_backend": "mineru|paddleocr",
          "parser_task_id": "<batch_id or paddleocr-fallback-...>",
          "status": "done|failed",
          "message": "<human-readable summary>",
          "received_at": "<ISO8601 UTC>",
          "warnings": ["<warning_code>"]
        }
        ```
        Notes:
        - Do NOT include any of: `download_url`, `full_zip_url`, `file_urls`.
        - Do NOT include any local filesystem paths.
      - `parsing_manifest` with hybrid spill policy, exact JSON shape:
        ```json
        {
          "schema_version": 1,
          "markdown_object_key": "<document_id>/parsing/parsed_markdown.md",
          "images_prefix": "<document_id>/parsing/images/",
          "image_count": 123,
          "image_object_keys": ["..."],
          "image_keys_manifest_object_key": "<document_id>/parsing/image_keys_manifest.json",
          "image_keys_manifest_sha256": "<hex>",
          "content_type": {
            "markdown": "text/markdown",
            "image": "image/jpeg"
          }
        }
        ```
        Rules:
        - If `image_count <= 200`: persist `image_object_keys` and set manifest_object_key fields to null/omit.
        - If `image_count > 200`: omit `image_object_keys` (or store only a short prefix list of first 5 for debug) AND persist `image_keys_manifest_object_key` + sha256.
        - Store object_keys/prefixes only; do NOT store URLs.
  6) Ensure `parsing_manifest` only contains object_keys / prefixes, never URLs.

  **Must NOT do**:
  - Must not write `mineru_folder` raw filesystem paths into manifest unless explicitly allowed (store relative path or omit). Prefer: store `mineru_folder` for debugging only, but mark as local-path, not URL.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: integrates MinerU, MinIO, Postgres, idempotency.
  - Skills: [`systematic-debugging`, `verification-before-completion`] 

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 5,6 | Blocked By: 2,3

  **References**:
  - MinerU pipeline: `src/domain/mineru/component.py`
  - Parsing agent: `src/domain/agent/document_parsing.py`
  - MinIO helpers: `src/infrastructure/minio.py` (buckets: `minio_uploads_bucket="literature-uploads"`, `minio_results_bucket="processed-results"` in `src/config.py`)
  - Postgres update API: `src/infrastructure/postgres.py::update_paper_task`

  **Acceptance Criteria**:
  - [ ] Running parsing task writes object_keys to MinIO and JSONB fields to Postgres; no URLs stored.

  **QA Scenarios**:
  ```
  Scenario: Parse PDF end-to-end
    Tool: Bash
    Steps:
      1) Start infra stack
      2) Enqueue parsing.parse_document.v1 with a known PDF in MinIO
      3) Poll paper_tasks row
    Expected:
      - mineru_response_sanitized IS NOT NULL
      - parsing_manifest IS NOT NULL
      - parsing_manifest contains only object_keys/prefixes
    Evidence: .sisyphus/evidence/task-4-parsing-e2e.txt

  Scenario: Idempotent replay
    Tool: Bash
    Steps:
      1) Run same task twice with same idempotency_key
    Expected:
      - Second run does not duplicate artifacts
      - DB state remains consistent
    Evidence: .sisyphus/evidence/task-4-idempotency.txt
  ```

- [ ] 5. Implement translation microservice worker

  **What to do**:
  1) Create `src/microservices/translation/` with Celery task `translation.translate_markdown.v1` + FastAPI health/metrics.
  2) Input: `{paper_task_id, document_id, markdown_object_key, schema_version, idempotency_key}`.
  3) Fetch markdown bytes from MinIO, run existing translation toolchain (`src/agents/parsing/translation_tool.py` + `src/tools/external/translation_api.py`).
   4) Write output English markdown to deterministic object_key: `{document_id}/en_format.md` (match existing monolith convention in `src/services/task_manager.py`).
  5) Update `processing_steps.translation` status and `workflow_status`.

  **Must NOT do**:
  - Must not store translated markdown text in Postgres.

  **Recommended Agent Profile**:
  - Category: `unspecified-high`
  - Skills: [`test-driven-development`]

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 6 | Blocked By: 3,4

  **References**:
  - Translation wrappers: `src/agents/parsing/translation_tool.py`, `src/tools/external/translation_api.py`
  - Existing monolith behavior: `src/services/task_manager.py::run_node_translation`

  **Acceptance Criteria**:
  - [ ] Translation task produces English markdown object_key and updates progress in Postgres.

  **QA Scenarios**:
  ```
  Scenario: Translate non-English markdown
    Tool: Bash
    Steps:
      1) Put a small markdown file in MinIO
      2) Run translation.translate_markdown.v1
    Expected: Output object exists; DB updated; no URLs stored
    Evidence: .sisyphus/evidence/task-5-translation.txt

  Scenario: Skip English
    Tool: Bash
    Steps:
      1) Run task with English markdown
    Expected: Marks translation step SKIPPED; workflow_status advances appropriately
    Evidence: .sisyphus/evidence/task-5-skip-en.txt
  ```

- [ ] 6. Implement extraction microservice worker

  **What to do**:
  1) Create `src/microservices/extraction/` with Celery task `extraction.extract_evidence.v1` + FastAPI health/metrics.
  2) Input: `{paper_task_id, document_id, en_markdown_object_key, image_prefix_or_keys, schema_version, idempotency_key}`.
  3) Fetch inputs from MinIO, run existing extraction tool/agent (`src/agents/extraction/extraction_tool.py`).
  4) Write evidence output JSON to deterministic key `{document_id}/ps3_evidence.json`.
  5) Update `processing_steps.extraction` only; **do not** mark adjudication completed (fix existing coupling).

  **Must NOT do**:
  - Must not set adjudication step status here.

  **Recommended Agent Profile**:
  - Category: `deep`
  - Skills: [`systematic-debugging`]

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 7 | Blocked By: 3,5

  **References**:
  - Extraction wrappers: `src/agents/extraction/extraction_tool.py`
  - Bug to remove: `src/services/task_manager.py::run_node_extraction` currently marks adjudication completed.

  **Acceptance Criteria**:
  - [ ] Extraction task writes evidence JSON to MinIO and updates only extraction-related progress.

  **QA Scenarios**:
  ```
  Scenario: Extract evidence from translated markdown
    Tool: Bash
    Steps:
      1) Seed MinIO with en markdown + images
      2) Run extraction.extract_evidence.v1
    Expected: ps3_evidence.json exists; DB updated; adjudication step untouched
    Evidence: .sisyphus/evidence/task-6-extraction.txt

  Scenario: Retryable failure classification
    Tool: Bash
    Steps:
      1) Simulate transient MinIO failure (mock)
    Expected: Task retries according to policy; eventual success updates DB
    Evidence: .sisyphus/evidence/task-6-retry.txt
  ```

- [ ] 7. Update orchestrator/supervisor to dispatch microservice tasks + migrate status semantics

  **What to do**:
  1) Update `src/services/task_manager.py` and/or `src/agents/supervisor.py` to:
     - Replace in-process parsing/translation/extraction execution with `celery_app.send_task(...)` to microservice task names.
     - Use only IDs + object_keys in messages.
  2) Resolve supervisor status semantics:
     - `SupervisorState.workflow_status` is `str` and supervisor currently uses lowercase literals `"completed"` / `"failed"`.
     - Align supervisor to new enum values (`SUCCESS` / `FAILURE`) and ensure all writes to DB use the new values.
  3) Handle human review:
     - User state machine does not include `PENDING_REVIEW`. Keep `requires_human_review` boolean as the flag, and keep `workflow_status` at the last completed stage (default to `ADJUDICATING`) while `requires_human_review=True`.
     - Keep API payload `status="pending_review"` if needed, but do not add a new workflow_status value.
  4) Remove/fix extraction→adjudication coupling globally.

  **Recommended Agent Profile**:
  - Category: `deep`
  - Skills: [`systematic-debugging`, `verification-before-completion`]

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: 8,9 | Blocked By: 4,5,6,1

  **References**:
  - Supervisor graph: `src/agents/supervisor.py`
  - Supervisor state: `src/state/global_state.py`
  - Orchestrator: `src/services/task_manager.py`

  **Acceptance Criteria**:
  - [ ] End-to-end pipeline (upload→success) works via microservices.
  - [ ] `paper_tasks.workflow_status` uses only new values; `requires_human_review` path works.

  **QA Scenarios**:
  ```
  Scenario: Upload PDF triggers microservice chain
    Tool: Bash
    Steps:
      1) Call upload endpoint
      2) Observe Celery tasks enqueued to q.parsing/q.translation/q.extraction
    Expected: paper_task progresses through statuses and completes
    Evidence: .sisyphus/evidence/task-7-e2e.txt

  Scenario: Human review gating
    Tool: Bash
    Steps:
      1) Force arbitration to set requires_human_review
    Expected: workflow_status remains stable; API returns pending_review status
    Evidence: .sisyphus/evidence/task-7-human-review.txt
  ```

- [ ] 8. Enforce “no URLs in Postgres” across persistence paths

  **What to do**:
  1) Identify all DB writes that store `parsing_metadata` / `PipelineFiles` or similar structures.
  2) Ensure persisted JSON excludes URL keys:
     - in logs (`paper_task_logs.payload`)
     - in new `mineru_response_sanitized` / `parsing_manifest`
     - in any `tasks.result` / `paper_tasks.node_trace`
  3) Update API layer to generate URLs on the fly from object_keys:
     - For example, `f"{cfg.api_prefix}/results/{document_id}/{object_key}"`.

  **Recommended Agent Profile**:
  - Category: `unspecified-high`
  - Skills: [`systematic-debugging`]

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: 9 | Blocked By: 4,7

  **References**:
  - Current URL generation: `src/services/task_manager.py::_store_parsing_artifacts_in_minio`, `_store_outputs_in_minio`
  - API status response: `src/api/routes/task.py::get_task_status`

  **Acceptance Criteria**:
  - [ ] Grep over DB JSON payloads in tests shows no `http` or `/results/` stored.

  **QA Scenarios**:
  ```
  Scenario: Verify persisted payloads contain no URLs
    Tool: Bash
    Steps:
      1) Run integration test that stores parsing metadata
      2) Query DB JSONB for 'http' and '/results/'
    Expected: 0 matches
    Evidence: .sisyphus/evidence/task-8-no-urls.txt
  ```

- [ ] 9. Observability baseline: metrics + correlation IDs

  **What to do**:
   1) Add `prometheus_client` (REQUIRED) to deps. Do NOT add `prometheus-fastapi-instrumentator` (keep dependencies minimal; implement FastAPI metrics endpoint manually using `prometheus_client`).
  2) For orchestrator and each microservice FastAPI app:
     - Expose `/metrics`.
  3) Add Celery signal instrumentation:
     - task runtime histogram by stage
     - success/failure/retry counters by stage + error_code
  4) Add correlation IDs:
     - propagate `{paper_task_id, document_id, request_id, celery_task_id}` in logs.

  **Must NOT do**:
  - Do not label Prometheus metrics with `document_id` (cardinality risk).

  **Recommended Agent Profile**:
  - Category: `unspecified-high`
  - Skills: [`verification-before-completion`]

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: 10 | Blocked By: 7

  **References**:
  - FastAPI entrypoint: `main.py`
  - Health checks: `src/health.py`

  **Acceptance Criteria**:
  - [ ] `/metrics` responds for each service.

  **QA Scenarios**:
  ```
  Scenario: Metrics endpoint availability
    Tool: Bash
    Steps:
      1) Start services
      2) curl /metrics
    Expected: 200 OK and Prometheus text format
    Evidence: .sisyphus/evidence/task-9-metrics.txt
  ```

- [ ] 10. Integration + contract + idempotency test suite for microservices

  **What to do**:
  1) Add contract tests validating DTO envelopes against golden payloads.
  2) Add idempotency tests: run same stage twice and assert no duplication.
  3) Add integration tests that spin up Postgres/Redis/MinIO using `database/podman-compose.yml` (or docker-compose) and run a worker.
  4) Add migration tests for old→new workflow_status coercion/backfill.

  **Recommended Agent Profile**:
  - Category: `deep`
  - Skills: [`test-driven-development`, `verification-before-completion`]

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: — | Blocked By: 4,5,6,7,8

  **Acceptance Criteria**:
  - [ ] `pytest -q` passes.

  **QA Scenarios**:
  ```
  Scenario: End-to-end integration
    Tool: Bash
    Steps:
      1) Start infra stack
      2) Run integration pytest markers
    Expected: PASS
    Evidence: .sisyphus/evidence/task-10-integration.txt
  ```

## Final Verification Wave (4 parallel agents, ALL must APPROVE)
- [ ] F1. Plan Compliance Audit — oracle
- [ ] F2. Code Quality Review — unspecified-high
- [ ] F3. Real Manual QA — unspecified-high
- [ ] F4. Scope Fidelity Check — deep

## Commit Strategy
- Frequent atomic commits per numbered task.
- Suggested prefixes:
  - `feat(workflow-status): ...`
  - `feat(db): ...`
  - `feat(celery): ...`
  - `feat(parsing-svc): ...`
  - `feat(translation-svc): ...`
  - `feat(extraction-svc): ...`
  - `test(contracts): ...`

## Success Criteria
- New microservice pipeline runs end-to-end.
- Backend stores no URLs in Postgres.
- `workflow_status` uses the new user-facing state machine values.
- MinerU response and parsing manifest are persisted per requirements.
