# ACMG PS3/BS3 Workflow Optimization (Docs-Aligned Microservice Cutover)

## TL;DR
> **Summary**: Align the PS3/BS3 backend plan to the frozen docs in `docs/` and the current codebase by delivering a 6-node single-paper LangGraph/Celery workflow, request-level aggregation, parser/translation/extraction microservices, durable provenance, and the v1.0 status/error/retry contracts.
> **Primary constraints from frozen specs**:
> - Workflow is fixed to **6 nodes**: acquisition → parsing → translation → extraction → ACMG classification → arbitration
> - Request status set is **exactly** `queued/running/partial_failed/failed/success`
> - Paper status set is **exactly** `queued/running/success/failed`
> - Every `request_id` and `paper_task_id` is **UUIDv4**
> - Celery unit of execution is **one task per paper**
> - Parser fallback is **MinerU → PaddleOCR-VL-1.5**
> - Translation/extraction/arbitration model routing must follow `docs/TECH_STACK.md`
> - Output must preserve **full evidence-source explainability** and return `failed + error_code + log_link` on failures
> **Repository constraints from `AGENTS.md`**:
> - Use **uv** only
> - Keep business code in `src/`, tests in `tests/`, docs in `docs/`
> - Update `progress.txt` after each milestone
> - Record debugging/troubleshooting lessons in `lesson.md`
> - Logging must use **loguru** and log files must live under `logs/`
> **Effort**: XL
> **Parallel**: YES — 5 waves
> **Critical path**: contracts/constants alignment → data model/status migration → parsing microservice persistence → translation/extraction cutover → supervisor/API/status aggregation → verification and release evidence

## Why this plan was updated
The previous `.sisyphus` plan was partially based on older assumptions and code-local terminology. The frozen product specs now take priority. This updated plan treats the following documents as authoritative in this order:
1. `docs/PRD.md`
2. `docs/BACKEND_STRUCTURE.md`
3. `docs/APP_FLOW.md`
4. `docs/TECH_STACK.md`
5. `docs/IMPLEMENTATION_PLAN.md`
6. `docs/CONSTANTS.md`
7. `docs/CHANGE_CONTROL.md`

## Codebase reality check (2026-03-22)
### Current structure already present
- Entry points: `main.py`, `src/main.py`, `app.py`
- Business code roots already exist: `src/api`, `src/application`, `src/domain`, `src/infrastructure`, `src/services`, `src/state`
- Tests already centralized under `tests/`
- Main orchestration lives in `src/agents/supervisor.py`
- Task execution and many pipeline details currently live in `src/services/task_manager.py`

### Current gaps vs frozen docs
1. `src/agents/supervisor.py` still uses non-doc status literals like `completed` / `failed` for workflow progression.
2. Current runtime shape appears to be an 8-node internal graph (`route_by_source`, `interaction`, `acquisition`, `parsing`, `translation`, `extraction`, `reasoning`, `arbitration`, finalize paths), while the product contract is a 6-node business workflow.
3. The docs require request-level and paper-level public states, but the code also carries internal workflow/progress concepts that need explicit mapping instead of leaking raw internals.
4. `docs/BACKEND_STRUCTURE.md` defines five layers (`api`, `application`, `domain`, `infrastructure`, `infra`) and the repo already contains `application/`; plan work should prefer that target shape instead of growing more logic in `services/` unless intentionally transitional.
5. Logging currently writes `logs/app_YYYYMMDD.log`; repository rules require timestamped log files under `logs/` using loguru. This needs explicit convergence work.
6. Release acceptance and backward compatibility now require complete provenance, source trace, retry policy, retention policy, and change-control discipline.

## Locked decisions for this plan
1. **Spec-first**: if implementation and docs disagree, update implementation toward docs unless the docs are formally changed.
2. **6-node public contract, richer internal execution allowed**: internal helper nodes may exist, but API/database/public progress must map cleanly to the 6-node business workflow.
3. **Microservices stay in-repo first**: create parser/translation/extraction service modules inside this repo before any multi-repo split.
4. **Postgres is canonical for user-visible state**; Celery result backend is not a UX source of truth.
5. **MinIO/Postgres provenance stores object keys and trace data, not presigned URLs**.
6. **Migration safety over refactor purity**: introduce compatibility shims where needed, then cut over.
7. **No silent scope drift**: any change to statuses, retries, retention, error codes, or acceptance metrics requires matching docs + change-control updates.

## Final target architecture
### Public workflow contract (must match docs)
1. Acquisition
2. Parsing
3. Translation
4. Extraction
5. ACMG Classification
6. Arbitration

### Service boundaries
- **Main service**: FastAPI + request aggregation + upload/candidate APIs + Celery orchestration + traceable JSON responses
- **pdf-parser-service**: MinerU first, PaddleOCR fallback, writes markdown/jpg to MinIO and parser metadata to PostgreSQL
- **translation-service**: translate non-English markdown to English, write aligned output to MinIO/Qdrant/PostgreSQL
- **evidence-extraction-service**: entity/relation/experiment extraction + retrieval augmentation
- **KG service**: separate service triggered by Celery events, reading PostgreSQL and updating Neo4j

### Canonical state model
- **Request states**: `queued/running/partial_failed/failed/success`
- **Paper states**: `queued/running/success/failed`
- **Internal processing steps**: allowed for progress UI and diagnostics, but must map to the public contract without inventing unsupported public states

### Mandatory data/provenance outcomes
- Persist natural-language task form and structured metadata
- Persist `source_trace`, node input/output summaries, evidence spans, alignment coordinates, timing, and status
- Persist parser outputs/manifest without storing URLs
- Return `log_link` as a signed temporary URL with 24h validity and 1/minute reissue limit

## Workstreams
1. **Contract alignment** — statuses, IDs, error codes, retries, provenance, API response shape
2. **Data model + storage alignment** — request/paper/evidence/alignment/log fields and migration safety
3. **Workflow cutover** — 6-node business flow with request aggregation and one Celery task per paper
4. **Microservice extraction** — parser/translation/extraction microservices with deterministic contracts
5. **Compliance + observability** — retention, logs, metrics, signed links, change-control, progress tracking
6. **Verification** — unit, contract, integration, acceptance-set, and rollback evidence

## Execution waves
### Wave 0 — Freeze the contracts before code moves
Goal: remove ambiguity so later implementation cannot drift.

Deliverables:
- Single mapping document from current code terms to frozen product terms
- Explicit public/internal state translation rules
- Task/message DTO envelope definitions with `schema_version`
- File-path list of exactly where status, retry, error, and provenance logic currently lives

Blocking outputs:
- No implementation starts before the state/error/retry mapping is written down.
- No microservice task name or payload is introduced ad hoc.

### Wave 1 — Data and status convergence
Goal: make persistence and API responses reflect frozen status/error/retry rules.

Deliverables:
- UUIDv4 enforcement for `request_id` and `paper_task_id`
- Request/paper status convergence in DB, enums, serializers, and tests
- Persistence fields for parser metadata/manifest/source trace/alignment evidence as required by docs
- Compatibility layer for reading older rows during migration

### Wave 2 — Parsing microservice and artifact persistence
Goal: deliver the most constrained stage first because downstream work depends on parser outputs.

Deliverables:
- Dedicated parsing Celery task + minimal service app
- MinerU first, PaddleOCR fallback
- Markdown/jpg artifacts in MinIO
- Sanitized parser response JSON + parsing manifest persisted to PostgreSQL
- DOCX terminal failure behavior

### Wave 3 — Translation and extraction microservices
Goal: make multilingual and evidence steps conform to v1.0 rules.

Deliverables:
- Translation task that skips English, translates non-English, writes English markdown to MinIO
- Qdrant BGE-M3 writes and PostgreSQL sentence alignment persistence
- HGVS autocorrect warning path (`HGVS_AUTOCORRECT_FAILED`)
- Extraction task using the existing extraction toolchain with proper evidence output storage and no adjudication coupling

### Wave 4 — Orchestrator/API/request aggregation cutover
Goal: expose the new workflow through stable public contracts.

Deliverables:
- One Celery task per paper
- Request aggregation from multiple `paper_task_id`s
- Upload dedup rules with SHA-256 and `FILE_DUPLICATE`
- Candidate pagination constraints (<=20 total, page_size=5, selection 1..5)
- Failure response contract `status=failed + error_code + log_link`
- Status endpoints, log-link reissue endpoint, and traceable JSON output

### Wave 5 — KG integration, observability, acceptance, release evidence
Goal: finish the system obligations required by the docs, not just the happy path.

Deliverables:
- KG event emission and retry handling
- `/metrics` and correlation IDs
- retention/cleanup scripts
- progress/lesson documentation updates per milestone
- acceptance-run evidence for 6-language support, >=95% literature success rate, <=30-minute per paper runtime

## Detailed task plan

### Task 1: Write the contract delta document inside the plan itself
**Files:**
- Modify: `.sisyphus/plans/acmg-ps3-bs3-workflow-optimization.md`
- Read for reference: `docs/PRD.md`, `docs/BACKEND_STRUCTURE.md`, `docs/APP_FLOW.md`, `docs/TECH_STACK.md`, `docs/CONSTANTS.md`, `docs/CHANGE_CONTROL.md`

**Implementation notes:**
- Capture exactly which code concepts are public contract vs internal implementation detail.
- Record a table mapping current code statuses and nodes to the frozen 6-node model.
- Record any doc-vs-code mismatches that must be resolved before or during implementation.

**Acceptance criteria:**
- Every later task in this plan references frozen terms, not improvised ones.
- There is no unresolved ambiguity about status sets, retry defaults, or error code source of truth.

**QA:**
- Tool: Bash
- Setup: none
- Run: `python - <<'PY'
from pathlib import Path
text = Path('.sisyphus/plans/acmg-ps3-bs3-workflow-optimization.md').read_text()
assert 'queued/running/partial_failed/failed/success' in text
assert 'queued/running/success/failed' in text
assert 'docs/PRD.md' in text and 'docs/CONSTANTS.md' in text
print('contract delta plan assertions passed')
PY`
- Expected: script prints `contract delta plan assertions passed`

### Task 2: Normalize status and ID contracts across code paths
**Files:**
- Modify: `src/services/enum.py`
- Modify: `src/agents/supervisor.py`
- Modify: `src/state/global_state.py`
- Modify: `src/api/routes/task.py`
- Modify: `src/services/task_manager.py`
- Test: `tests/test_state_transitions.py`
- Test: `tests/test_state_schema.py`

**Implementation notes:**
- Keep public request/paper statuses exactly as frozen in docs.
- If an internal `workflow_status` enum remains, define it as an internal progress concept and provide a one-way mapping to public states.
- Remove lowercase public terminal states like `completed` from user-facing outputs.
- Ensure all generated IDs are UUIDv4.

**Acceptance criteria:**
- Public API responses never expose unsupported status values.
- Existing rows can still be read during migration.
- State transition tests cover partial failure, all-success, and all-duplicate cases.

**QA:**
- Tool: Bash
- Setup: none
- Run:
  1. `uv run pytest tests/test_state_transitions.py -q`
  2. `uv run pytest tests/test_state_schema.py -q`
- Expected: both commands pass; no public status outside the frozen request/paper sets appears in assertions or serialized payload fixtures

### Task 3: Align persistence models with the documented minimum fields
**Files:**
- Modify: `src/infrastructure/models.py`
- Modify: `src/infrastructure/postgres.py`
- Modify: `database/alembic/versions/<new_revision>.py`
- Test: `tests/integration/` migration coverage or dedicated migration tests

**Implementation notes:**
- Ensure `task_requests`, `paper_tasks`, `paper_task_logs`, `sentence_alignments`, and evidence output storage meet the documented minimum field set.
- Add parser metadata fields needed for sanitized MinerU persistence.
- Preserve `source_trace`, `duplicate_of`, `fulltext_unavailable`, warnings, and trace chain requirements.
- Avoid storing presigned URLs in structured JSON columns.

**Acceptance criteria:**
- New schema can be applied and local bootstrap still works.
- Required provenance fields exist and are writable.

**QA:**
- Tool: Bash
- Setup:
  1. `./database/scripts/dbctl.sh up`
  2. `./database/scripts/dbctl.sh init`
- Run:
  1. `uv run pytest tests/integration -k "migration or postgres or schema" -q`
  2. `uv run python - <<'PY'
from src.infrastructure.models import PaperTask
required = {'duplicate_of', 'fulltext_unavailable'}
actual = {c.name for c in PaperTask.__table__.columns}
missing = required - actual
assert not missing, missing
print('PaperTask required columns present')
PY`
- Expected: migration-related tests pass and the schema inspection script prints `PaperTask required columns present`

### Task 4: Extract parser work into an in-repo microservice
**Files:**
- Create: `src/microservices/parsing/__init__.py`
- Create: `src/microservices/parsing/app.py`
- Create: `src/microservices/parsing/tasks.py`
- Modify: `src/celery_app.py`
- Modify: `src/domain/agent/document_parsing.py`
- Modify: `src/infrastructure/minio.py`
- Modify: `src/services/task_manager.py`
- Test: `tests/test_agents_parsing.py`
- Test: `tests/test_supervisor_integration.py` or create `tests/integration/test_parsing_microservice.py`

**Implementation notes:**
- Use versioned task names and explicit queues.
- Celery payloads must carry IDs/object keys, not raw markdown/image blobs.
- PDF path: MinerU then PaddleOCR fallback.
- DOCX parse failure remains terminal.
- Persist sanitized parser response and manifest to PostgreSQL; artifacts go to MinIO.

**Acceptance criteria:**
- Parsing succeeds for a sample PDF with persisted parser metadata.
- DOCX failure path yields the documented error contract.
- No URL fields are persisted in parser JSON.

**QA:**
- Tool: Bash
- Setup:
  1. `./database/scripts/dbctl.sh up`
  2. `./database/scripts/dbctl.sh init`
- Run:
  1. `uv run pytest tests/test_agents_parsing.py -q`
  2. `uv run pytest tests/test_supervisor_integration.py -k parsing -q` or `uv run pytest tests/integration/test_parsing_microservice.py -q`
- Expected: parsing tests pass; at least one integration path proves parser artifact persistence and DOCX terminal-failure handling

### Task 5: Extract translation work into an in-repo microservice
**Files:**
- Create: `src/microservices/translation/__init__.py`
- Create: `src/microservices/translation/app.py`
- Create: `src/microservices/translation/tasks.py`
- Modify: `src/celery_app.py`
- Modify: `src/agents/parsing/translation_tool.py`
- Modify: `src/tools/external/translation_api.py`
- Modify: `src/services/task_manager.py`
- Test: `tests/test_agents_parsing.py`
- Test: `tests/test_literature_unified_workflow.py`

**Implementation notes:**
- Route translation work to `MT_MODEL`.
- Skip translation when source text is English.
- Persist English markdown to MinIO and sentence alignments to PostgreSQL.
- Vectorize with BGE-M3 into Qdrant.
- If HGVS autocorrect fails, continue with warning `HGVS_AUTOCORRECT_FAILED`.

**Acceptance criteria:**
- English documents skip translation.
- Non-English documents produce English markdown, Qdrant vectors, and alignment rows.
- Warning behavior matches docs.

**QA:**
- Tool: Bash
- Setup:
  1. `./database/scripts/dbctl.sh up`
  2. `./database/scripts/dbctl.sh init`
- Run:
  1. `uv run pytest tests/test_agents_parsing.py -k translation -q`
  2. `uv run pytest tests/test_literature_unified_workflow.py -k translation -q`
- Expected: one test proves English skip behavior, one test proves translated markdown/alignment persistence, and warning handling is asserted for HGVS correction failure

### Task 6: Extract evidence work into an in-repo microservice
**Files:**
- Create: `src/microservices/extraction/__init__.py`
- Create: `src/microservices/extraction/app.py`
- Create: `src/microservices/extraction/tasks.py`
- Modify: `src/celery_app.py`
- Modify: `src/agents/extraction/`
- Modify: `src/services/task_manager.py`
- Test: `tests/test_agents_extraction.py`
- Test: `tests/test_pipeline_parity.py`

**Implementation notes:**
- Route evidence extraction to `EVIDENCE_MODEL` plus the existing scispaCy/LlamaIndex stack.
- Preserve retrieval strategy expectations from docs: keyword + vector + reranker.
- Persist evidence outputs, confidence, errors, and trace chain.
- Do not let extraction mark arbitration complete.

**Acceptance criteria:**
- Evidence JSON is persisted and traceable.
- Extraction state updates only extraction-related progress.

**QA:**
- Tool: Bash
- Setup:
  1. `./database/scripts/dbctl.sh up`
  2. `./database/scripts/dbctl.sh init`
- Run:
  1. `uv run pytest tests/test_agents_extraction.py -q`
  2. `uv run pytest tests/test_pipeline_parity.py -k extraction -q`
- Expected: extraction tests pass and parity/integration checks confirm arbitration is not prematurely marked complete
### Task 7: Rework supervisor/orchestrator around the 6-node business flow
**Files:**
- Modify: `src/agents/supervisor.py`
- Modify: `src/services/task_manager.py`
- Modify: `src/domain/literature/`
- Modify: `src/application/` modules as needed for request orchestration
- Test: `tests/test_supervisor.py`
- Test: `tests/test_supervisor_e2e.py`
- Test: `tests/test_supervisor_integration.py`

**Implementation notes:**
- Keep internal helper nodes if needed, but ensure the persisted/public progression is the 6-node contract.
- One Celery task per paper.
- Respect source selection flow: upload skips acquisition, search path goes through candidate selection.
- Support `fulltext_unavailable=true` fallback to metadata+abstract evidence.

**Acceptance criteria:**
- Upload and literature-selection paths both work.
- Public node/status summaries align with docs.
- Arbitration remains the final business node before success/failure aggregation.

**QA:**
- Tool: Bash
- Setup:
  1. `./database/scripts/dbctl.sh up`
  2. `./database/scripts/dbctl.sh init`
- Run:
  1. `uv run pytest tests/test_supervisor.py -q`
  2. `uv run pytest tests/test_supervisor_e2e.py -q`
  3. `uv run pytest tests/test_supervisor_integration.py -q`
- Expected: supervisor unit/e2e/integration tests pass and the visible node progression maps cleanly to acquisition → parsing → translation → extraction → ACMG classification → arbitration

### Task 8: Implement request aggregation and dedup exactly per docs
**Files:**
- Modify: `src/api/routes/core.py`
- Modify: `src/api/routes/task.py`
- Modify: `src/services/task_manager.py`
- Modify: `src/infrastructure/postgres.py`
- Test: `tests/test_task_manager_pdf_download.py`
- Test: `tests/test_api_gateway_download.py`
- Test: `tests/test_supervisor_integration.py`

**Implementation notes:**
- Enforce upload limits: max 10 files, 10MB each, 50MB total.
- Deduplicate by global SHA-256.
- Duplicate behavior must create a new `paper_task_id`, set paper status `success`, set `error_code=FILE_DUPLICATE`, set `duplicate_of`, and skip pipeline nodes.
- If all papers in a request are duplicates, request status must still be `success`.
- Empty execute selection with no upload must return `failed + INPUT_INVALID`.

**Acceptance criteria:**
- Duplicate uploads count in both success numerator and denominator.
- Request aggregation correctly produces `partial_failed`, `failed`, and `success`.

**QA:**
- Tool: Bash
- Setup:
  1. `./database/scripts/dbctl.sh up`
  2. `./database/scripts/dbctl.sh init`
- Run:
  1. `uv run pytest tests/test_task_manager_pdf_download.py -q`
  2. `uv run pytest tests/test_api_gateway_download.py -q`
  3. `uv run pytest tests/test_supervisor_integration.py -k "duplicate or request" -q`
- Expected: dedup and request aggregation tests pass, including all-duplicate → request success and mixed outcome → `partial_failed`

### Task 9: Implement API contracts for status, logs, and traceable output
**Files:**
- Modify: `src/api/routes/task.py`
- Modify: `src/api/dependencies.py`
- Modify: `main.py`
- Modify: `src/health.py`
- Test: `tests/test_stream_route.py`
- Test: `tests/test_stream_supervisor.py`
- Test: `tests/test_node_error_handling.py`

**Implementation notes:**
- Required endpoints per docs: create request, list candidates, execute request, request status, paper-task status, log-link reissue.
- Failure payload must always include `status=failed`, `error_code`, and `log_link`.
- Log-link reissue must enforce 1/minute per `paper_task_id` and 24-hour signed URL validity.
- JSON output must include node input/output summaries, evidence coordinates, source links/metadata, and alignment positions.

**Acceptance criteria:**
- API contracts match documented fields and limits.
- Old clients tolerate additive provenance fields.

**QA:**
- Tool: Bash
- Setup:
  1. `./database/scripts/dbctl.sh up`
  2. `./database/scripts/dbctl.sh init`
- Run:
  1. `uv run pytest tests/test_stream_route.py -q`
  2. `uv run pytest tests/test_stream_supervisor.py -q`
  3. `uv run pytest tests/test_node_error_handling.py -q`
- Expected: API/stream/error-contract tests pass and failed responses include `status`, `error_code`, and `log_link`

### Task 10: Align observability, retention, and runtime hygiene with repo rules
**Files:**
- Modify: `main.py`
- Modify: `src/health.py`
- Modify: `scripts/` cleanup or ops scripts
- Modify: `progress.txt`
- Modify: `lesson.md`
- Test: `tests/` coverage for retention/ops logic where practical

**Implementation notes:**
- Keep loguru as the logging framework.
- Write logs under `logs/` with timestamped filenames that satisfy repository rules.
- Add `/metrics` endpoints and stage metrics without high-cardinality labels.
- Add cleanup paths for 7-day parser intermediates and runtime logs.
- After each implementation milestone, update `progress.txt`; for debugging sessions, record outcomes in `lesson.md`.

**Acceptance criteria:**
- Runtime logs and cleanup behavior match repo policy.
- Milestone-tracking files are part of the implementation process, not an afterthought.

**QA:**
- Tool: Bash
- Setup: none
- Run:
  1. `uv run pytest tests -k "health or retention or minio_config_validation" -q`
  2. `uv run python - <<'PY'
from pathlib import Path
assert Path('progress.txt').exists(), 'progress.txt missing'
print('progress.txt exists')
PY`
- Expected: relevant observability/retention tests pass and the repository tracking file check passes

### Task 11: Implement KG event contract and backfill path
**Files:**
- Modify: `src/domain/graph/sync.py`
- Modify: KG event producers/consumers under `src/` or adjacent service code
- Modify: `scripts/` backfill scripts
- Test: `tests/integration/` KG event coverage

**Implementation notes:**
- Main service emits Celery events after pipeline completion.
- KG reads PostgreSQL and updates Neo4j.
- Backfill must resume from checkpoint.
- KG retry queue uses ACMG/arbitration retry policy.

**Acceptance criteria:**
- Incremental eventing works.
- Backfill resumes cleanly after interruption.

**QA:**
- Tool: Bash
- Setup:
  1. `./database/scripts/dbctl.sh up`
  2. `./database/scripts/dbctl.sh init`
- Run:
  1. `uv run pytest tests/integration -k "graph or kg or backfill" -q`
- Expected: KG-related integration tests pass, including retry/backfill resume assertions where implemented

### Task 12: Verification and release gate
**Files:**
- Modify/Add tests under `tests/`
- Modify: `docs/CHANGE_CONTROL.md` if any contract changed during implementation
- Modify: `progress.txt`
- Modify: `lesson.md` as needed

**Implementation notes:**
- Verify unit, contract, integration, and acceptance scenarios.
- Use `uv run pytest` for test execution.
- Confirm six-language support, >=95% literature-level success rate, <=30-minute paper runtime, and traceable output chain.
- If statuses/error codes/retries/retention changed, update docs before shipping.

**Acceptance criteria:**
- Release evidence exists for all acceptance gates.
- No undocumented contract drift remains.

**QA:**
- Tool: Bash
- Setup:
  1. `./database/scripts/dbctl.sh up`
  2. `./database/scripts/dbctl.sh init`
- Run:
  1. `uv run pytest -q`
  2. `uv run python - <<'PY'
from pathlib import Path
text = Path('docs/CHANGE_CONTROL.md').read_text()
assert 'v1.0' in text
print('change control checked')
PY`
- Expected: full test suite passes or only documented pre-existing failures remain; change-control validation script prints `change control checked`
## Cross-cutting invariants
1. Never store presigned URLs or frontend result URLs in Postgres JSON payloads.
2. Never let Celery result backend become the user-visible source of truth.
3. Never break the frozen request/paper status sets.
4. Never bypass UUIDv4 generation.
5. Never use non-`uv` dependency workflows.
6. Never expand scope beyond PS3/BS3 for ACMG v1.0.
7. Never degrade country mapping to language-only approximation.
8. Never reopen business tasks automatically; reopen is ops-script-only and reuses the original `paper_task_id`.

## Required verification matrix
### Contract verification
- `tests/test_state_schema.py`
- `tests/test_state_transitions.py`
- API payload tests for error contract and status serialization

### Workflow verification
- upload path
- search/candidate/execute path
- duplicate upload path
- `fulltext_unavailable` fallback path
- DOCX parse terminal failure path
- translation skip vs translate path
- arbitration/human-review path if retained as an internal flag

### Data verification
- UUIDv4 IDs
- SHA-256 dedup
- alignment persistence
- evidence trace chain persistence
- no-URL JSON persistence checks

### Acceptance verification
- fixed acceptance set mechanics
- success-rate computation includes `FILE_DUPLICATE`
- per-paper duration measured from worker start
- six-language path coverage

## Commit strategy for implementation phase
- `feat(status-contract): ...`
- `feat(schema): ...`
- `feat(parsing-service): ...`
- `feat(translation-service): ...`
- `feat(extraction-service): ...`
- `feat(request-aggregation): ...`
- `feat(api-contract): ...`
- `feat(observability): ...`
- `test(release-gate): ...`

## Definition of done
- Public API behavior matches `docs/PRD.md`, `docs/BACKEND_STRUCTURE.md`, `docs/APP_FLOW.md`, `docs/TECH_STACK.md`, `docs/CONSTANTS.md`, and `docs/CHANGE_CONTROL.md`.
- The 6-node PS3/BS3 workflow runs with one Celery task per paper and request-level aggregation.
- Parser/translation/extraction service boundaries are in place and testable.
- Dedup, retry, failure, log-link, retention, and provenance rules are implemented as documented.
- `progress.txt` and `lesson.md` are updated during execution, not retroactively.
- Verification evidence proves the release acceptance gate, or clearly records any gap.

## Open risks to watch during implementation
1. Existing code may depend on undocumented internal workflow states; isolate rather than leak them.
2. Migration may require dual-read compatibility for legacy status/progress fields.
3. Logging filename policy in `main.py` currently appears non-compliant with repo rules and may need coordinated change.
4. `src/application/` vs `src/services/` ownership needs deliberate convergence to avoid deepening architectural drift.
5. The current supervisor graph includes internal nodes not named in the docs; mapping mistakes here can create frontend/status confusion.
6. Acceptance-gate metrics require real measurement plumbing, not inferred values.

