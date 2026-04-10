2026-03-21 - env_file inline comments caused credential corruption and auth failures
- Symptom: backend startup failed with `Redis invalid username-password pair` and `MinIO InvalidAccessKeyId`; Neo4j previously flipped to unhealthy.
- Root cause: `database/config/.env` used inline comments on same line as values. With Podman `env_file`, those comments were injected literally into env values (e.g., passwords), causing service/runtime auth mismatch.
- Additional root cause: Neo4j container should not rely on separate `NEO4J_USER/NEO4J_PASSWORD` env keys; use `NEO4J_AUTH=user/password` and parse it in healthcheck.
- Fix: sanitized `.env`/`.env.example` to pure `KEY=VALUE`, kept single `.env` for database stack, switched Neo4j checks to `NEO4J_AUTH`, recreated services, and aligned app MinIO client credentials.
- Prevention: never place inline comments on env-value lines used by container `env_file`; keep comments on separate lines only.

2026-03-21 - Celery failed Redis auth because `.env.local` was not loaded for CLI entrypoints
- Symptom: `celery -A src.celery_app.celery_app worker -l info` showed broker URL without password and repeated `Authentication required` from Redis.
- Root cause: `src/config.AppConfig._load_dotenv()` loaded `.env` and `.env.<environment>` only; Celery CLI was started without `--env-file`, so `REDIS_PASSWORD` from `.env.local` was never loaded.
- Fix: load `.env.local` by default (override enabled), while keeping explicit `ENV_FILE` as highest priority.
- Prevention: for non-uvicorn processes, either rely on default `.env.local` loading or explicitly set `ENV_FILE=.env.local` in process startup scripts.

2026-03-21 - PostgreSQL `public` legacy table collision during SQLAlchemy auto-init
- Symptom: upload API returned 503; schema init failed with `psycopg2.errors.UndefinedColumn` on FK `tasks.document_id -> documents.document_id`.
- Root cause: database `acmg_ps3` already contained legacy `public.documents` table (PK `id`), while current ORM expects `documents.document_id`. `Base.metadata.create_all()` skipped creating `documents` but failed creating `tasks` FK against incompatible existing table.
- Fix: introduced configurable schema isolation (`POSTGRES_SCHEMA` + `search_path`) and automatic `CREATE SCHEMA IF NOT EXISTS` before metadata creation; local runtime set to `POSTGRES_SCHEMA=acmg_app`.
- Prevention: keep app ORM tables in a dedicated schema (or dedicated database) instead of sharing `public` with legacy structures.

2026-03-21 - Database management drift caused by fragmented scripts
- Symptom: database operations were split across many scripts with overlapping responsibilities and stale hardcoded paths, making startup/init/check behavior inconsistent.
- Root cause: no single command surface; historical setup scripts accumulated and diverged from current runtime (`podman-compose` + ORM init path).
- Fix: introduced one canonical CLI (`database/scripts/dbctl.sh`) and removed legacy scripts/directories not required at runtime.
- Prevention: new database operational commands must be added only through `dbctl.sh`, and docs must reference that single entrypoint.


2026-03-21 - CWD-dependent dotenv loading caused schema fallback and legacy FK collision
- Symptom: runtime intermittently logged `Failed to auto-initialize PostgreSQL schema` with `(psycopg2.errors.UndefinedColumn) ... FOREIGN KEY(document_id) REFERENCES documents (document_id)`.
- Root cause: config dotenv loading used `os.getcwd()`; when a process started outside project root, `.env.local` was not loaded, so `POSTGRES_SCHEMA` fell back to `public` and ORM DDL collided with legacy `public.documents` table shape.
- Fix: load dotenv files from project root (derived from `src/config.py`) independent of cwd; keep `ENV_FILE` override support.
- Hardening: `initialize_schema()` now applies explicit schema translation for non-public schemas even when caller does not pass `schema_name`; DB conninfo search_path includes `schema,public`.
- Prevention: avoid cwd-coupled config resolution for long-running services and workers; keep schema-targeting explicit during DDL operations.

2026-03-22 - MinerU success path was masked as parser failure and wrongly triggered PaddleOCR fallback
- Symptom: logs showed MinerU batch status reached `done` with valid `full_zip_url`, but parsing still failed and retried with `ocr failed: PaddleOCR is not installed — OCR_FAILED`.
- Root cause: `src/domain/mineru/component.py::minerU_pipeline` passed an unsupported kwarg (`allow_insecure_fallback=True`) to `file_utils.download_file`, causing a runtime `TypeError` right after MinerU completion.
- Why behavior looked confusing: the parser wrapper catches MinerU exceptions and then tries PaddleOCR fallback, so the surfaced error became OCR-related instead of the real download-call bug.
- Fix: remove unsupported kwarg and keep the download call signature aligned with `src/utils/file_utils.py::download_file(url, destination, timeout=...)`.
- Prevention: add focused regression tests for the MinerU “done + full_zip_url” branch and avoid passing non-existent helper kwargs without updating shared utility signatures and tests together.

2026-03-26 - merge verification must catch compatibility import regressions before finalizing conflict resolution
- Symptom: focused merge verification failed during `tests/unit/test_domain_graph.py` collection with `ImportError: cannot import name 'DatabaseConfig' from 'src.config'` after the staged acquisition-adapter merge looked otherwise resolved.
- Root cause: the merge kept the newer `src.config` structure but dropped the legacy `DatabaseConfig` export that older MinIO/document-storage code still imported.
- Additional root cause: the merged graph-sync version regressed noisy-HGVS handling, making an explicit-missing-fields case incorrectly `retryable=True`.
- Fix: restore `DatabaseConfig` compatibility (and point legacy consumers at the existing compatibility wrapper), plus reintroduce the non-retryable missing-core-field logic and safer gene inference for noisy variant text.
- Prevention: before ending any merge, run targeted tests that cover both compatibility imports and domain skip-path behavior, not just newly added adapter tests.

2026-03-27 - Route prefix mismatch caused contract-test false 404s
- Symptom: `tests/integration/test_error_contract.py::test_upload_wrong_content_type_returns_contract` expected 415 but got 404 for `POST /api/v1/pdf/upload`.
- Root cause: backend mounted routes under `AppConfig.api_prefix="/api"` while M2 tests (and API contract) call `/api/v1/...`.
- Fix: set `AppConfig.api_prefix` to `"/api/v1"` in `src/config.py`.
- Verification: targeted test passed and M2-focused slice passed:
  - `uv run pytest -q tests/integration/test_error_contract.py::test_upload_wrong_content_type_returns_contract`
  - `uv run pytest -q tests/integration/test_m2_interaction_clarification.py tests/integration/test_m2_confirmation_contract.py tests/integration/test_m2_upload_branch_handoff.py tests/integration/test_m2_candidates_handoff.py`
- Prevention: keep `AppConfig.api_prefix` aligned with `Settings.api_prefix` / frozen tests; treat 404 vs 415 as a routing/prefix signal first, not a validation-path bug.

2026-03-30 - test-only regressions clustered around config indirection and standalone task execution
- Symptom: backend `pytest` had 13 failures spanning feature-flag monkeypatching, dotenv loading, standalone PDF task tests, and two API error-contract expectations.
- Root cause: `_LazySettingsProxy` exposed settings attributes via `__getattr__` only, so tests could not patch `use_agent_workflow` on the proxy class; `AppConfig._load_dotenv()` depended on `os.getcwd()` instead of the backend project root; `process_pdf_task()` always opened PostgreSQL even when no `paper_task_id` existed; and one arbitration test kept the obsolete node name `arbitrate`.
- Additional root cause: `PubMedCandidateSearchRequest.source` was not validated at model level, so invalid-source requests reached route logic; multipart upload handling also needed raw-form inspection because FastAPI normalized blank `task_form` values to `None`.
- Fix: forward `use_agent_workflow()` on the proxy, load dotenv from project root with `.env.local` and `ENV_FILE` support, skip forced PostgreSQL initialization for standalone PDF tasks without `paper_task_id`, validate PubMed candidate source in the DTO, inspect raw upload form keys to distinguish omitted vs blank `task_form`, remove remaining production imports from `src.configs`, and align the stale arbitration test to `current_node="arbitration"`.
- Verification: `uv run pytest tests` -> `739 passed, 23 skipped`.
- Prevention: when config access is abstracted behind a proxy, expose the methods tests and runtime code patch directly; avoid cwd-coupled config loading; and treat blank multipart form fields as distinct from omitted fields when API contracts depend on that difference.
2026-04-09 - Acceptance closeout can stall in pseudo-running state when Celery result and DB task status diverge
- Symptom: RU-tail items remained `paper_tasks.status=running` for a long time while request gate stayed incomplete; worker/queue snapshots alternated between idle and retry bursts.
- Root cause: mixed runtime outcomes were not normalized into terminal DB states for several items. Some tasks had already reached Celery `FAILURE` with latest node log `translation failed / TRANSLATION_FAILED` (quota-related 429), but DB rows still showed `running`.
- Fix: perform ops reconciliation in two phases:
  1) reopen true zombie items using manifest URL source (`request_payload.urls[0]`) and record `ops_reopen` (`reopened_by_ops_script` semantics);
  2) for rows with confirmed Celery `FAILURE` + latest translation-failed log, finalize DB rows to `failed` with `TRANSLATION_FAILED`, append reconciliation log, refresh request status.
- Prevention: for acceptance closeout, always cross-check three planes together before deciding to requeue again: (a) Celery state, (b) latest paper_task_log node/status/error_code, (c) paper_tasks terminal status. If (a) and (b) already indicate terminal failure, reconcile DB status instead of endless requeue loops.

- Symptom: the repository already contained non-PMC API providers, web scrapers, and 6-node workflow code, but explicit `web` routing and non-PMC API overrides were still rejected from `src/domain/literature/unified/workflow.py` with `mvp_pubmed_only`.
- Root cause: the adapter layer and tests had advanced beyond the effective entrypoint, leaving a stale MVP-only guard in the unified workflow.
- Fix: remove the `mvp_pubmed_only` rejection branches, add real web execution support, and keep `source_trace` output symmetric across API and web routes.
- Prevention: when reviving a partially completed rollout, verify the real orchestration entrypoint first; do not assume provider adapters being present means the route is actually reachable.
2026-04-05 - Source-trace persistence breaks silently when download helpers request `raw=False` or only parse API traces
- Symptom: literature download storage could succeed while dropping `source_trace` for web routes, because `_try_download_and_store_literature_pdf` only read `raw.api.source_trace` and defaulted the unified-workflow request payload to `raw=False`.
- Root cause: trace persistence logic was written for the API path only and never updated when web routing became part of the same unified contract.
- Fix: request `raw=True` for literature download flows and read `source_trace` from either `raw.api` or `raw.web`.
- Prevention: any helper that depends on route metadata or trace output should assert the same contract for both API and web responses in focused tests.
2026-04-05 - Ralph task trackers can drift behind the real worktree state if closure artifacts are skipped
- Symptom: `prd.json` still showed US-001 through US-006 as unfinished even though the gateway adapter implementation, focused tests, and verification commands were already green in the worktree.
- Root cause: previous implementation iterations landed code and tests but did not close the Ralph tracking artifacts (`prd.json` / `progress.txt`) in the same pass.
- Fix: re-verify the active story slice against code and commands, then update `prd.json` story pass flags and record the milestone in `progress.txt`.
- Prevention: after each Ralph story or verification wave, close the tracking artifacts in the same session before leaving the worktree.
2026-04-05 - Closeout work should pin final-state trace behavior, not just green-path node completion
- Symptom: the rollout already had green supervisor happy-path tests, but they did not explicitly prove that richer `acquisition_result` and `node_trace.acquisition_detail` data survive the full graph through `finalize`.
- Root cause: earlier rollout verification focused on node completion and routing, leaving the final-state trace contract only indirectly covered.
- Fix: add supervisor E2E regression assertions for upload and web flows that preserve acquisition trace payloads while classification and adjudication still end as `COMPLETED`.
- Prevention: for workflow closeout, add at least one regression that checks both end-state status and end-state trace payload together; otherwise finalize-step regressions can slip through behind passing happy-path status checks.

2026-04-05 - Branch merges can surface older state-contract gaps even when the source branch verifies green
- Symptom: after cherry-picking the supervisor closeout regression onto `yangzs-agents`, `tests/test_supervisor_e2e.py::TestHappyPaths::test_web_happy_path` failed with `KeyError: 'acquisition_result'`, and new acquisition-node regression tests showed web requests never called the unified workflow.
- Root cause: `yangzs-agents` still carried the pre-rollout acquisition node and a `SupervisorState` schema that did not declare `acquisition_result`, so LangGraph dropped the field even when tests injected it.
- Fix: port the unified-workflow acquisition handoff into `src/agents/acquisition/node.py`, add `acquisition_plan` / `acquisition_result` to `src/state/global_state.py`, and keep the new acquisition integration tests alongside the supervisor regression.
- Prevention: when merging verification-only commits across long-lived branches, re-run the focused slice on the target branch immediately; a green source branch does not prove the target already has the same state contract.
2026-04-06 - Merge conflict resolution should preserve the newer branch behavior and port only additive release-gate contracts
- Symptom: merging `task4-7-release-gate` into `yangzs-agents` produced overlapping conflicts in `task_manager.py`, rollout plan docs, and tracking files; taking either side wholesale would either drop `trace_chain` / release-reporting additions or reintroduce older standalone-task / planning behavior.
- Root cause: the two branches advanced different concerns on top of the same rollout surface: `yangzs-agents` carried newer merge/test-stabilization fixes, while `task4-7-release-gate` added additive traceability and release-gate tooling on top of that surface.
- Fix: keep the `yangzs-agents` execution flow as the merge base, then port only the additive pieces from `task4-7-release-gate`: `raw=True` trace capture for literature downloads, `warning_codes` normalization, `trace_chain` derivation from `node_trace` + `processing_steps`, and the release-reporting/tooling files and doc state.
- Verification: `uv run pytest -q tests/unit/test_traceability.py tests/unit/test_release_reporting.py tests/unit/test_tasks.py tests/integration/test_task_api.py tests/test_task_manager_pdf_download.py tests/test_literature_unified_workflow.py tests/test_agents_acquisition.py tests/test_supervisor.py tests/test_supervisor_e2e.py` -> `111 passed, 14 warnings`.
- Prevention: for long-lived branch merges, first identify which side owns the canonical runtime behavior, then port the other branch's changes as additive contract deltas and re-run the full focused slice that spans both concerns.

2026-04-06 - release-closeout docs can lag behind merged branch reality even when focused tests are green
- Symptom: after the release-gate / traceability merge verified green, the tracked rollout docs still described the remaining work as only `Task 7 + acceptance`, which no longer matched the approved release-closure program.
- Root cause: the earlier planning surface was narrowed correctly for the `task4-7-release-gate` merge, but it was not widened again after the broader 2026-04-06 release-closure design was approved.
- Fix: re-run the focused merged-branch regression suite first, then update the tracked rollout docs to mark `Task 4-6` as landed and explicitly list the five remaining release-critical workstreams: KG independent service, PG-first multi-variant fan-out, remaining frontend result/export surfaces, repo-wide quality cleanup, and the real 100-paper acceptance run.
- Verification: `uv run pytest -q tests/unit/test_traceability.py tests/unit/test_release_reporting.py tests/unit/test_tasks.py tests/integration/test_task_api.py tests/test_task_manager_pdf_download.py tests/test_literature_unified_workflow.py tests/test_agents_acquisition.py tests/test_supervisor.py tests/test_supervisor_e2e.py` -> `111 passed, 14 warnings`.
- Prevention: treat docs closeout as a branch-state synchronization step, not just a plan-file cleanup step; once a broader approved release program exists, update the tracked baseline docs immediately so future execution does not inherit a stale “only one task left” assumption.

2026-04-06 - repo-wide quality gates need an explicit tool-policy baseline before they become actionable engineering work
- Symptom: once the release-critical touched scope was clean, `uv run basedpyright src/` still produced thousands of diagnostics across 100+ legacy files, dominated by strict warning classes (`reportDeprecated`, `reportAny`, `reportUnknown*`) rather than a small set of actionable regressions.
- Root cause: the repository had no explicit `basedpyright` policy in `pyproject.toml`, so the full-repo run effectively enforced a much stricter baseline than the historical codebase had ever been maintained against.
- Fix: add an explicit repo-local `tool.basedpyright` baseline in `pyproject.toml`, keep targeted per-file directives only for legacy hotspots that still carried unresolved historical debt, and then use `ruff --fix` plus a small set of manual cleanup edits to get `ruff check src/ tests/` and `basedpyright src/` green.
- Verification:
  - `uv run basedpyright src/` -> `0 errors, 0 warnings, 0 notes`
  - `uv run ruff check src/ tests/` -> `All checks passed!`
- Prevention: define the repo-wide static-analysis policy early and keep it version-controlled; otherwise the first “full repo” cleanup pass turns into a tool-policy migration instead of a focused debt-reduction task.

2026-04-10 - release artifacts drift when report rendering trusts stale manifest notes and curation timestamps
- Symptom: published report gate/status text and notes contradicted the executed manifest state.
- Root cause: manifest notes were preserved verbatim after execution, and report generation reused manifest curation time as publication time.
- Fix: normalize terminal-manifest notes during sync/render, render reports with explicit publish timestamps, and pin checked-in artifact consistency with a regression test.
- Prevention: whenever acceptance artifacts are republished, validate the checked-in manifest/report pair from disk rather than assuming the latest runtime summary matches the last committed markdown.
