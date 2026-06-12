# Lesson Log

## 2026-06-12: "Illegal header value b'Bearer '" in chat when REASONING_LLM_API_KEY unset

**Problem**: The ant-bubble chat displayed `[Error] Illegal header value b'Bearer '` when the user sent a message. The chat stopped working entirely.

**Investigation**: Traced the error chain from the frontend's SSE handler (`sse.ts` prepends `[Error]` to backend error events), through the SSE stream endpoint (`chat.py` → `chat_service.py`), into `ReasoningLLMProvider.stream()` which constructs `Authorization: f"Bearer {self._api_key}"`. The `reasoning_llm_api_key` env var defaults to `""`, so the header value becomes `Bearer ` (with space but no token). httpx rejects this as an invalid header value.

**Root cause**: `ReasoningLLMProvider.__init__()` read `cfg.reasoning.api_key` directly without fallback to the generic LLM config (`cfg.llm.api_key`), and made no validation before constructing the HTTP header. When `REASONING_LLM_API_KEY` was unset, the empty string produced the illegal `Bearer ` header value, and the cryptic httpx error propagated to the user as-is.

**Fix**:
1. In `__init__`, fall back empty reasoning-specific fields (`api_key`, `model`, `base_url`) to the generic LLM config via `or` — so if only `FAST_LLM_API_KEY` is set, chat still works.
2. Added `_ensure_configured()` helper that raises `ValueError` with a clear message (`"Reasoning LLM API key is not configured. Set REASONING_LLM_API_KEY or FAST_LLM_API_KEY."`) before any HTTP call.
3. Called `_ensure_configured()` at the top of both `generate()` and `stream()`.

**Prevention**: Any LLM provider that constructs `Authorization: Bearer {key}` headers must validate the key is non-empty before the HTTP call. Fallback chains (reasoning → generic) reduce the blast radius of a missing config and make the system self-healing when the same key is reused across LLM tiers.

## 2026-06-12: Pipeline status poll misclassified running jobs as failed

**Problem**: The frontend showed the pipeline badge as `failed` while the backend pipeline was still running. The visible symptom came from `/api/v1/pipeline/runs/{id}/status`, which could turn a DB-loaded `RUNNING` state into `FAILED` when the current worker did not have a local asyncio task for that run.

**Investigation**: Traced the frontend polling path (`usePipelineStatus`, `ChatView`, `PipelineStatusCard`) and confirmed it only renders the backend status it receives. Then inspected `PipelineRunner.get_last_state()`: after cache miss and DB load, it treated any active status without a local task as an orphaned run and immediately relabeled it `FAILED`. Startup already runs `recover_orphaned_runs()`, so the query-time relabeling was redundant and unsafe in multi-worker / reload setups.

**Root cause**: Query-time orphan detection used only local process state (`is_running()`) to infer global pipeline liveness. In a distributed or multi-worker deployment, a healthy pipeline can be running on another worker while the current worker has no task handle, which produced a false `failed` state.

**Fix**: Removed the relabeling block from `PipelineRunner.get_last_state()`. The status endpoint now returns the persisted DB state unchanged. Orphan recovery remains handled at startup by `recover_orphaned_runs()`. Updated the runner regression test to assert that a DB `RUNNING` state stays `RUNNING` and is not persisted as `FAILED`.

**Prevention**: Do not mutate durable pipeline status during read-only status polling. Recovery logic belongs in startup repair or explicit reconciliation, not in the hot path that feeds the UI.

## 2026-06-12: Pipeline Phase 2 per_block_check failure on Chinese medical documents — LLM reproduced source alongside translation

**Problem**: A Chinese medical case-report PDF (`5例Rett综合征样表型患儿的基因突变分析`) made it through Phase 1 (MinerU parsing) and entered Phase 2 (translate). The LLM (mimo-v2.5-pro via xiaomimimo.com) returned text that was still 82% Chinese (31/38 blocks > 40% per-block threshold). The new `_check_block_language` validator correctly raised `TranslationError("per_block_check — 31/38 blocks still in zh (82% > 40% threshold)")` and the pipeline was aborted. Frontend labeled this as "Extraction ✕" (because Phase 2 is translate+extract and the failure happened in the translate stage). Self-review grew text 6455→17303 chars (2.7x), indicating the LLM reproduced the Chinese source alongside its English translation — a known failure mode for medical/scientific Chinese documents with many untranslatable proper nouns (MECP2, Rett syndrome, IVIG, etc.).

**Investigation**: Read `logs/2026-06-12_102940.log` for run 3957d7f8. The `translate_segments` stage ran with `lang=zh` and produced 64→49 translated blocks, but 31/38 text/title blocks still had >15% CJK characters. The self-review step (`mimo-v2.5-pro`) grew the text 2.7x without actually translating, suggesting the LLM echoed the source content. The per-block check (added in the 2026-05-20 round 2 fixes per `_BLOCK_SOURCE_LANG_THRESHOLD = 0.15` and `_UNTRANSLATED_BLOCK_RATIO = 0.40` in `postprocess.py`) caught the issue and aborted.

**Root cause**: The mimo-v2.5-pro model has a tendency to reproduce source-language text in its Chinese→English translation output for medical/scientific documents, even when instructed to translate. The translation validator correctly detected this, but there was no recovery path — the pipeline failed outright.

**Fix**: Added a strict-retry path in `translate_to_result()` that catches `TranslationError` with `"per_block_check"` in the message and re-runs the translation pipeline once with a stricter prompt. The new `get_full_document_translate_prompt(marked_source, terminology, strict=True)` appends an explicit `[STRICT ENGLISH-ONLY RETRY]` block that:
- Demands output MUST be entirely English
- Enumerates the only allowed non-English content (pinyin names, established English scientific terms, direct quotes)
- Explicitly forbids reproducing Chinese source alongside translation
- Forbids bilingual output format

The retry is bounded by `_MAX_PER_BLOCK_RETRIES = 1` to prevent runaway LLM cost on pathological inputs. If the strict retry also fails, the `TranslationError` propagates as before. Other `TranslationError` types (e.g. `unchanged`, `non_english_output`) are NOT retried — they indicate different failure modes that wouldn't benefit from a stronger prompt.

**Files changed**:
- `backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/prompts/translate.py` — added `strict` parameter to `get_full_document_translate_prompt()` with the STRICT ENGLISH-ONLY block
- `backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/translator.py` — added `_MAX_PER_BLOCK_RETRIES = 1` constant, threaded `strict` through `_translate_blocks()` → `translate_segments()` → `run_pipeline()`, added retry logic in `translate_to_result()`
- `backend/tests/core/cross_lingual_process_and_extract_evidence/test_round2_fixes.py` — added `TestStrictRetryPrompt` (2 tests) and `TestPerBlockRetryBehavior` (3 tests)

**Verification**: All 59 focused translation tests pass (54 existing + 5 new). Ruff clean on changed files. The retry path activates only when the per-block check fails with the specific `per_block_check` error — other translation failures propagate immediately.

**Prevention**: When integrating LLMs for translation, always include a recovery path for partial-translation failures. The strict prompt pattern (re-running with an explicit "ALL output must be English" directive) is a robust, low-cost fix for models that occasionally echo source content. When adding new validation rules, consider whether a softer fallback (retry with stronger prompt) is more useful than a hard failure for known-bounded LLM behaviors.

## 2026-06-11: Chat session creation 500 — DB schema NOT NULL vs code nullable mismatch

**Problem**: `POST /api/v1/chat/sessions` returned 500 (Internal Server Error) when called without `processing_run_id`. The frontend creates standalone chat sessions for the standalone chat mode, which sends an empty body `{}`.

**Investigation**: Server log showed `POST /api/v1/chat/sessions -> 500` with no error detail in logs (500 too fast — 2ms — bypassed structured error handlers). Direct test of `ChatService.create_session()` revealed:
- `sqlalchemy.exc.IntegrityError`: null value in column `processing_run_id` of relation `chat_sessions` violates not-null constraint
- The ORM model `ChatSession` defines `processing_run_id: Mapped[UUID | None]` (`nullable=True`)
- The API route accepts `CreateSessionRequest` with `processing_run_id: UUID | None = None`
- But the DB migration set `processing_run_id` as `NOT NULL`

**Root cause**: Schema/migration mismatch. The code consistently treats `processing_run_id` as optional (standalone chat sessions don't belong to any processing run), but the migration didn't match.

**Fix**: `ALTER TABLE chat_sessions ALTER COLUMN processing_run_id DROP NOT NULL`

**Prevention**: When running new migrations, verify that nullable columns in the ORM model match the migration output. After-the-fact schema fixes should be added as new migration scripts.

## 2026-06-11: Code review evaluated wrong branch — worktree isolation matters

**Problem**: A code review document claimed the target-anchored extraction implementation was ~15% complete, listing every feature as missing. The review evaluated the `dev` branch (main repo), not the worktree (`docs/target-anchored-extraction-plan`) where all 11 feature commits landed.

**Investigation**: Ran `grep` on every claim against the worktree files. Every single assertion was wrong — `ExtractionTarget` was a `BaseModel` with full normalization (not a frozen dataclass), `EvidenceRole` had correct values (PRIMARY/PHENOTYPE/COMPARATOR/CONTEXT, not GENE/DISEASE/VARIANT), `stages/role_routing.py` existed, `TargetEntityGuard` existed, all test files existed and passed (119/119).

**Root cause**: The reviewer checked out the `dev` branch instead of the worktree branch. Git worktrees have separate working directories but share the same `.git` — the branch name matters. The review document was generated without verifying which branch/working directory was being analyzed.

**Solution**: Wrote a corrected review with verified line references for every checkpoint, committed to the worktree's `docs/codereview/`.

**Prevention**: When reviewing code in a worktree, always verify the current branch with `git branch --show-current` before reading files. When presenting a code review, include the branch name and at least one verified line reference per claim. Never assume the main working directory reflects the feature branch.

## 2026-06-08: Plan review caught unsafe highlight fallback and throwaway frontend steps

**Problem**: The bilingual comparison implementation plan proposed an `_build_highlight` rewrite that would regress valid-start/oversized-end clamping and remove the short-value guard too broadly. The frontend plan also added inline JSX that a later task immediately deleted, and the component sketch omitted key null/zero-length rendering cases.

**Investigation**: Checked the existing `test_build_highlight_clamps_invalid_offsets` fixture and the group-detail test rows. Confirmed that the original/translated rows in the existing fixture use different `field_id` values, so `traces[0].translated_value` would be `None`. Reviewed the frontend component sketch and verified the missing null guard, conditional chip issue, and lack of component tests.

**Root cause**: The plan mixed desired behavior with incomplete code sketches and did not re-evaluate existing tests before claiming the test suite would pass.

**Solution**: Revised the plan to preserve clamping, use explicit offset parsing, add bounded value-anchor matching, keep ambiguous single-letter values unhighlighted, add a paired-field backend test, build `BilingualComparison` directly, and add Vitest component tests for null, marked, and zero-length highlight states.

**Prevention**: When writing implementation plans with code snippets, verify them against existing tests and fixtures before stating expected pass/fail counts. Avoid temporary implementation steps that are immediately deleted by later tasks.

## 2026-06-05: 推理模型 max_tokens 不足导致空响应

**Problem**: 使用 mimo-v2.5（推理模型）调用 LLM 时，设置 `max_tokens=200` 返回空 content。567 个 PDF 全部判断失败。

**Root cause**: 推理模型会先生成 reasoning_content（内部推理链），再生成 content。200 token 不够完成推理+输出，导致 `finish_reason: length` 且 content 为空字符串。

**Fix**: 将 max_tokens 增大到 4096，为推理链和输出留足空间。

**Prevention**: 使用推理模型时，max_tokens 应设为 4096 或更高。首次调用新模型时，先做单次测试确认返回正常。

## 2026-06-05: PDF 批量重命名时哈希冲突导致文件覆盖丢失

**Problem**: 批量重命名 222 个 PDF 时，2 个文件因标题相同且前 4096 字节哈希相同被覆盖（en 1 个, ja 1 个）。

**Root cause**: `file_hash()` 只读取文件前 4096 字节计算 SHA256，两个不同 PDF 的前缀内容相同导致哈希一致，加上 LLM 提取的标题也相同，生成了完全相同的新文件名。`os.rename()` 会静默覆盖目标文件。

**Fix**:
1. `file_hash()` 改为读取完整文件内容计算哈希
2. 重命名前检查目标文件是否已存在，存在则跳过并报错
3. 功能已集成到 `rett_download.py` 的 `cleanup` 和 `rename` 子命令

**Prevention**: 批量文件操作必须有防覆盖机制。哈希应基于完整文件内容。重命名前先 dry-run 检查重复项。

## 2026-06-05: 在线获取 Phase 3 内容关卡缺失导致下载不相关文献

**Problem**: `online_acquisition_workflow` 的 Phase 3（LLM 内容关卡）是空占位符，下载的 PDF 没有经过内容相关性验证，导致 Rett 综合征 benchmark 中 61% (345/567) 的 PDF 与主题无关。

**Root cause**: workflow.py Phase 3 注释写着 *"can be added as a future enhancement"*，实际未实现。搜索返回的候选基于关键词匹配，API 结果中混有大量不相关文献。

**Fix**:
1. 新建 `relevance_gate.py` 核心模块，提供可复用的 LLM 相关性检查
2. workflow.py Phase 3 调用 `run_relevance_gate()`，下载后自动过滤不相关文件
3. `OnlineAcquisitionRequest` 新增 `relevance_gate: bool = True` 开关
4. benchmark `cmd_cleanup` 重构为核心模块委托

**Prevention**: 涉及外部数据获取的 pipeline 必须有内容验证环节，不能仅依赖关键词匹配。LLM 内容关卡应在 download action 中默认启用。

## 2026-05-12: maturin develop not overwriting .so file

**Problem**: After `cargo clean` + `maturin develop --release`, the installed `.so` in the venv was stale — only 4 of 8 MinerU functions were available in Python.

**Root cause**: `maturin develop` reported success ("Installed rust-io-0.1.0") but the wheel installation did not overwrite the existing `.so` file in `.venv/lib/python3.12/site-packages/rust_io/`. MD5 hash of the installed file differed from the newly built one. Additionally, `patchelf` was missing, causing rpath warnings.

**Fix**:
1. `uv pip install patchelf` to fix rpath handling
2. Manual copy: `cp libs/rust-io/target/release/librust_io.so .venv/.../rust_io.cpython-312-x86_64-linux-gnu.so`
3. After patchelf install, need to verify `maturin develop` actually replaces the .so

**Prevention**: After `maturin develop`, always verify with `python -c "import rust_io.net as net; print(dir(net))"` that all expected functions are present. If functions are missing, manually copy the .so from `target/release/`.

## 2026-05-12: Code review — duplicate helpers and empty structured data

**Problem**: Code review found 3 blocking issues: (1) TableStructure populated with empty headers/rows, (2) _html_table_to_markdown duplicated verbatim in test and production, (3) test helper _parse_content_list diverged from production _parse_content_list_json (no figures/tables on PageContent).

**Root cause**: Initial implementation created test-only helper functions instead of importing from production. The test helper skipped _build_result path, so figures/tables were never populated through pages_from_raw. Table structured data was hardcoded as empty dict.

**Fix**:
1. Extracted _html_table_to_markdown, _html_table_to_structured, _block_to_markdown as module-level functions in mineru_parser.py (single source of truth)
2. _parse_content_list_json now calls _html_table_to_structured to populate real headers/rows
3. Test's _parse_content_list now routes through MinerUParser._parse_content_list_json + _build_result, exercising full production pipeline
4. Moved HTMLParser import to module level

**Prevention**: When implementing parsing logic, always route test helpers through production code paths. Don't duplicate utility functions — import from the production module. When populating structured data models, verify the fields contain real data, not empty defaults.

## 2026-05-14: Disabled invalid Codex MCP server

**Problem**: Codex global MCP configuration included `time`, but the current session did not expose a corresponding usable MCP tool while `codex mcp list` still showed it enabled.

**Investigation**: Checked `~/.codex/config.toml`, `~/.claude/settings.json`, VS Code MCP configuration, and `codex mcp list`. The active MCP entries were in Codex global config; `time` was the only configured MCP not available in this session.

**Root cause**: Stale/invalid global MCP server configuration for `time` remained in Codex config.

**Fix**: Removed the global MCP server with `codex mcp remove time` and verified the remaining MCP list.

**Prevention**: After adding or changing MCP servers, run `codex mcp list` and verify the tools exposed in the active session match configured entries.

## 2026-05-14: Skill files skipped due to missing YAML frontmatter

**Problem**: Codex skipped loading five skills because their `SKILL.md` files did not start with YAML frontmatter delimited by `---`.

**Investigation**: Checked known valid skill files and confirmed the expected format is a four-line header containing only `name` and `description`, followed by the Markdown body. Inspected the skipped files and found they started directly with `# ...` headings.

**Root cause**: The skill documents had valid body content but lacked the required metadata block, so the loader rejected them before reading the skill content.

**Fix**: Added `name` and `description` frontmatter to `ts-react`, `rust-dev`, `data-analysis`, `agent-dev`, and `bioinformatics` without changing their bodies.

**Prevention**: When adding or syncing skills, validate that every `SKILL.md` begins with `---`, has a valid hyphenated `name`, a trigger-focused `description`, and closes the frontmatter before the Markdown body.

## 2026-05-15: MinerU batch review exposed parser contract drift

**Problem**: Code review found a blocking type mismatch in `upload_local_files()` parameter annotations and inconsistent response validation between the new MinerU batch methods and the existing single-URL parser path.

**Investigation**: Re-ran the relevant parser tests, then added regression tests for non-zero `code` responses in `_create_task()` and `_poll_result()`. Confirmed the new `_require_success_response()` helper handled batch paths but not the legacy path.

**Root cause**: The batch feature was implemented incrementally and the legacy single-URL methods kept their older ad-hoc response handling. The shared response shape drifted across code paths.

**Solution**: Typed `model_version` and `extra_formats` with the MinerU Literals, refactored `_create_task()` and `_poll_result()` to reuse `_require_success_response()`, and added batch status property tests for `failed`, mixed, and empty states.

**Prevention**: When introducing shared protocol handling, refactor all callers onto the shared helper immediately. Add regression tests for both the new feature path and the legacy path before calling the change done.

## 2026-05-15: Final verification caught stale test import

**Problem**: Task 10 Ruff verification failed on `backend/tests/core/test_parse_document_config.py` with an unused `pytest` import.

**Investigation**: Re-read the Ruff output, inspected the test file, and checked the branch diff. The file did not use `pytest`, and the final verification command intentionally linted it.

**Root cause**: A stale import remained in a config test that was included in the plan's final lint scope.

**Solution**: Removed the unused import without changing test behavior.

**Prevention**: When a final lint command includes files outside the current feature diff, run the exact command early enough to catch pre-existing style drift before final checkpointing.

## 2026-05-18: Progress log overwrite during documentation work

**Problem**: While drafting the database design and implementation plan, `progress.txt` was briefly overwritten with a single new line instead of preserving the full project history.

**Investigation**: Compared the working tree against `git show HEAD:progress.txt` and confirmed the file in the tree had collapsed to one entry.

**Root cause**: The file was edited with an accidental whole-file replacement instead of an append-style update.

**Solution**: Restored the full historical log contents and appended the new database planning entries at the end.

**Prevention**: For append-only logs, always diff against `git show HEAD:<file>` before and after editing, and prefer targeted patch updates over whole-file replacement.

## 2026-05-18: Database MVP batch exposed worktree and tool-environment assumptions

**Problem**: Database implementation setup hit multiple execution issues before and during the first batch: a slash branch name conflicted with the repository's flat `feature` branch ref, an interrupted pytest run left the red-test state incomplete, and `uv run ruff` initially failed because Ruff was only available through the optional dev extra.

**Investigation**: Checked `git branch`, `.git/refs/heads`, `git worktree list`, running pytest processes, and `uv tree --depth 1`. Re-ran the targeted pytest commands from the isolated `database-mvp` worktree and confirmed the failures were setup/tooling issues rather than database code behavior.

**Root cause**: The implementation plan assumed a slash-style feature branch and default dev-tool availability, while this repo currently has a flat branch namespace conflict and installs Ruff under the `dev` extra.

**Solution**: Created the isolated worktree on the flat `database-mvp` branch, resumed from the exact red-test point after interruption, and used `uv run --extra dev ruff check ...` for lint verification.

**Prevention**: Before executing future written plans, verify branch namespace compatibility with `git branch --list`, confirm the worktree path is active before writing tests, and run dev tools through the same uv extras/groups declared in `pyproject.toml`.

## 2026-05-18: Database session helper default created unmanaged engine lifecycle

**Problem**: Code review found that `get_async_session()` created a new async engine when called without a session factory, then dropped the engine reference without disposing its connection pool.

**Investigation**: Re-read `backend/src/dao/connection.py` and confirmed the default path called `build_async_engine()` inside the context helper. The existing test only covered the custom factory path, so the unmanaged-engine path had no coverage.

**Root cause**: A convenience default hid resource ownership inside a dependency helper. Engine lifecycle belongs to application startup/shutdown or explicit test setup, not to a per-session context manager.

**Solution**: Removed the default path and made `get_async_session()` require an explicit session factory. Added a regression test that calling it without a factory raises `TypeError`.

**Prevention**: Avoid convenience constructors in lifecycle-sensitive DAO helpers. Tests should cover any fallback branch that allocates external resources, or that branch should not exist.

## 2026-05-18: Alembic script_location resolution is CWD-relative, not ini-relative

**Problem**: `script_location = migrations` in `database/alembic.ini` failed when running `uv run alembic` from `backend/` — Alembic resolved the path relative to CWD rather than the ini file directory.

**Investigation**: Tested with Python `Config.get_main_option('script_location')` and `ScriptDirectory.from_config()`. Confirmed that Alembic's `ScriptDirectory` resolves `script_location` from the current working directory, not from the ini file location, despite documentation suggesting otherwise.

**Root cause**: Alembic resolves relative `script_location` paths against the CWD where the Alembic command is invoked, not against the directory containing `alembic.ini`.

**Solution**: Used Alembic `%(here)s` interpolation which expands to the directory containing the ini file: `script_location = %(here)s/migrations`. This makes migration commands work regardless of CWD — both from repo root and from `backend/` directory.

**Prevention**: When setting up Alembic with a non-standard directory layout (ini file not at project root), always use `%(here)s` in `script_location` to avoid CWD-dependent resolution failures.

## 2026-05-18: Initial migration drifted from ORM metadata after review fixes

**Problem**: Code review found `canonical_evidence_items` in the initial Alembic migration was missing `current_best_status`, `conflict_flag`, and the `review_status` server default. The same review found `frontend_search_index` was attached to `Base.metadata`, which would make Alembic autogenerate treat the manual projection table as write-model drift.

**Investigation**: Compared `backend/src/dao/models.py`, `database/migrations/versions/*_init_mvp_schema.py`, and `backend/src/dao/search_index_repo.py`. Added migration capture tests that inspect `op.create_table("canonical_evidence_items", ...)` and a metadata isolation test for the search index table.

**Root cause**: The migration was manually written before the final ORM review fixes landed, and the read-model projection reused `Base.metadata` for convenience even though Alembic targets that metadata.

**Solution**: Added the missing canonical evidence columns/default to the initial migration, moved `frontend_search_index` to standalone `MetaData`, and added regression tests for both issues.

**Prevention**: When manually maintaining migrations, add tests that compare critical migration DDL against ORM metadata. Keep read-side/manual projection tables off Alembic target metadata unless they are intentionally migration-managed.

## 2026-05-18: Full backend pytest collection hit duplicate test module names

**Problem**: Running `uv run pytest` from `backend/` failed during collection with an import mismatch between `backend/services/model-server/tests/test_config.py` and `backend/tests/core/test_config.py`.

**Investigation**: The error happened before executing tests and reported that both files were imported as the same top-level module name `test_config`.

**Root cause**: Two test files in different directories share the same basename without package isolation, so pytest can import one as `test_config` and then reject the second file with the same module name.

**Solution**: Verified the database branch with the targeted suite `uv run pytest tests/core/test_database_config.py tests/dao -q`, which covers all changed backend database files. Ruff also passed for the changed backend database and migration files.

**Prevention**: Give duplicate test basenames package-qualified imports by adding `__init__.py` where appropriate, or rename one of the duplicate files before relying on repo-wide pytest collection.

## 2026-05-18: maturin develop picks wrong venv across worktrees

**Problem**: After merging feature branch to main worktree, `maturin develop --release` failed because it found Python 3.11 in `rust-io/.venv` (main worktree) while `uv.lock` requires Python>=3.12.

**Root cause**: Each worktree has its own `rust-io/.venv`. The main worktree's venv was created with Python 3.11; the feature worktree's venv had Python 3.12. After the merge updated `uv.lock` to require 3.12, the main worktree's local venv couldn't install.

**Fix**: Copy the `.so` from the feature worktree's build output to the main worktree's backend venv. Long-term: use `--manifest-path` with maturin to target the correct Python, or ensure all local venvs use the same Python version.

**Prevention**: After merging Rust changes across worktrees, rebuild in the target worktree with the correct Python version, or copy the `.so` explicitly.

## 2026-05-18: Database config default test read local dotenv files

**Problem**: After merging `database-mvp` into `dev`, `test_postgresql_and_redis_nested_config` failed because `Settings()` loaded `backend/.env.local` and saw `POSTGRES_USER=acmg_user` instead of the expected default empty user.

**Investigation**: The test cleared process environment variables with `monkeypatch.delenv`, but pydantic-settings still read configured dotenv files. The isolated database worktree did not have the same local dotenv file, so the targeted suite passed there and failed in the main worktree.

**Root cause**: The default-value test was not fully isolated from developer-local dotenv files.

**Solution**: Constructed `Settings(_env_file=None)` in the default-value test so it validates code defaults without reading `.env.local` or `.env`.

**Prevention**: For config tests that assert defaults, disable dotenv loading explicitly. Use environment variables only in tests that are intentionally validating env overrides.

## 2026-05-19: model-server VLM default config exposed stale 503 behavior

**Problem**: `POST /v1/chat/completions` on the running model-server returned `503 Service Unavailable` with `{"detail":"VLM service not available. Configure VLM_MODEL_ID to enable."}`.

**Investigation**: Checked the live process start time, `/health`, OpenAPI, `app/config.py`, `main.py`, and the model-server logs. The live `8001` process started on 2026-05-16 and was still running old wiring. The repo's `.env.local` also defined `VLM_MODEL`, not `VLM_MODEL_ID`, while `backend/services/model-server` only read `VLM_MODEL_ID`. Targeted tests failed because `app/config.py` defaulted `vlm_model_id` to the MinerU model and `vlm_image_analysis` to `True`, contradicting the tests and README.

**Root cause**: Two issues combined. First, model-server config defaults enabled VLM even when the environment did not configure it. Second, the long-lived 8001 process was not restarted after source changes, so it kept serving the stale 503 behavior.

**Solution**: Set `vlm_model_id` default to empty string and `vlm_image_analysis` default to `False`, added a regression test that `/v1/chat/completions` is absent from OpenAPI when `VLM_MODEL_ID` is unset, updated the model-server README to describe 404 vs 503 behavior correctly, and verified a fresh process returns 404 without VLM config and 400 when VLM is explicitly enabled but the request is text-only.

**Prevention**: Keep config defaults aligned with tests and docs, prefer explicit enablement for optional model services, and restart stale long-lived service processes after changing startup wiring. For runtime checks, confirm the live process start time matches the code on disk before trusting logs.

## 2026-05-20: model-server vLLM API and engine lifecycle drift

**Problem**: A fresh model-server process started successfully, but real `/v1/embeddings` and `/v1/rerank` calls failed with HTTP 500 or left `VLLM::EngineCore` child processes holding GPU memory after the parent process exited.

**Investigation**: Reproduced the failure with `uv run python main.py` plus HTTP requests. Logs showed `EngineArgs.__init__() got an unexpected keyword argument 'task'`, then later CUDA memory errors when loading rerank after embedding. Inspected local `vllm.LLM` signatures and GPU process state with `nvidia-smi`.

**Root cause**: The model-server used older vLLM constructor arguments (`task="embed"` / `task="score"`) while the installed vLLM 0.20.2 expects `runner="pooling"` and `convert="embed"` for embeddings. The service also kept vLLM engines resident after requests, which is not viable on a single 8GB GPU and can leave child EngineCore processes alive if not shut down.

**Solution**: Updated embedding/rerank vLLM calls to the current pooling API, changed rerank scoring to `score(query, documents)`, added `BaseModelService.unload()` to shut down `llm_engine.engine_core`, and call it from embedding, rerank, and VLM route `finally` blocks. Added regression tests for config path resolution, vLLM argument shape, scoring call shape, and engine shutdown.

**Prevention**: When integrating fast-moving inference libraries, inspect installed API signatures in the active `uv` environment before coding. Include live HTTP smoke tests that load real models, and always verify GPU process cleanup after vLLM failures or service shutdown.

## 2026-05-20: _trim_repetitive_content safety threshold too aggressive

**Problem**: `_trim_repetitive_content` had a `len(result) < 100` safety check that kept the original repetitive text when the unique content was short (<100 chars). This defeated deduplication for short documents with heavy repetition.

**Root cause**: Absolute character threshold (100) doesn't account for source document length. A short source with 5 repetitions produces a short trimmed result, triggering the false safety.

**Fix**: Changed to relative threshold: `len(result) < 30 and len(result) < len(text) * 0.10`. This keeps the original only when the trimmed result is both absolutely and relatively tiny.

**Also fixed**: The algorithm skipped ALL content after the first repeated heading, even content under first-occurrence headings. Rewrote to track heading+body blocks and only skip blocks with repeated headings.

## 2026-05-20: fix_word_boundary_redacted missing adjacent case

**Problem**: `fix_word_boundary_redacted` only handled mid-word `[REDACTED]` (e.g., `Re[REDACTED]ferences`) but not adjacent cases like `References [REDACTED]` where the LLM inserts `[REDACTED]` after common English section headings.

**Fix**: Added `_REDACTED_ADJ_HEADING_RE` pattern that matches `[REDACTED]` adjacent to common section headings (References, Abstract, Introduction, Methods, Results, Discussion, Conclusion, etc.) and strips it while preserving the heading.

## 2026-05-20: Translation output review — es/pt untranslated, REDACTED still broken in names

**Review scope**: All 24 documents in `backend/output/` across 6 source languages (en, ja, zh, es, pt, ru), all targeting English.

### Problem 1: es/ and pt/ translations completely failed (6 documents, CRITICAL)

All Spanish (es×3) and Portuguese (pt×3) documents were saved with source text identical to translated text. Translation validation correctly detected `translation_validation_failed: unchanged` and `translation_validation_failed: non_english_output`, but results were persisted anyway.

**Root cause**: LLM returned the input text verbatim instead of translating. Likely causes: (a) translation prompt insufficient, (b) LLM weaker at ES/PT→EN, (c) documents contain mixed-language content confusing the LLM.

**Fix needed**: Investigate translation prompt and add retry with explicit language instruction. Add post-translation check that blocks saving of completely untranslated output.

### Problem 2: [REDACTED] still inserted inside proper names (10 documents, HIGH)

Despite the 2026-05-20 fix for heading-adjacent [REDACTED], the formatter LLM continues to insert [REDACTED] inside transliterated proper names in ja→en and zh→en translations:
- "Takayuki [REDACTED]okia" (should be "Takayuki Motoki" from 元木崇之)
- "Takayuki [REDACTED]omotob" (should be "Takayuki Iwamoto" from 岩本高行)

The existing `_REDACTED_IN_WORD_RE` only matches when both sides are letters. In these cases, `[REDACTED]` is preceded by a space, so the regex misses it.

**Fix needed**: Extend the regex to match `[REDACTED]` at word boundaries (`\b\[REDACTED\](?=[A-Za-z])`). Also add negative examples with transliterated names to the formatter prompt.

### Problem 3: Block count mismatches across all non-en documents (20 documents, MEDIUM)

All translations have fewer blocks than originals (-12% to -50%). Image reference warnings in 3 documents suggest image blocks may be dropped.

### Problem 4: Empty terminology maps (13/20 documents, MEDIUM)

Only 7 documents have terminology maps. Terminology extraction may be skipped for some languages.

## 2026-05-23: Block-aware extract_evidence contract changes require localized compatibility fixes

**Problem**: Executing the block-aware evidence extraction plan required changing public contracts early (`ContentBlock`, `group_id`, `case_ids`, block-only `SourceLocation` defaults). Those changes immediately broke collection and risked rippling through unrelated extraction behavior if applied too broadly.

**Investigation**: Added task-specific failing tests first (`test_api_contracts.py`, `test_api_backward_compat.py`, prompt/stage regressions), then traced actual impact with targeted `rg` over `extract_evidence/` and its tests. Confirmed the first-batch surface was limited to contracts, `api.py`, prompt builders, catalog/special stages, and `EvidenceChainBuilder`.

**Root cause**: The existing module assumed text-only documents and single `case_id` chain output. The new plan introduces block-aware inputs and grouped chain semantics incrementally, so task-order mismatches can produce false failures unless each task updates the minimum dependent code.

**Solution**:
1. Added only the minimal local `ContentBlock` subset inside `extract_evidence/contracts.py`, without importing the upstream cross-lingual dataclass.
2. Updated `EvidenceChainBuilder` just enough to emit `case_ids` and `chain_level` while keeping current chain selection behavior unchanged.
3. Preserved API backward compatibility by parsing `blocks` locally and falling back cleanly when historical JSON has none.
4. Switched catalog/special prompts to block text only after adding targeted tests that assert prompt content and stage wiring.

**Prevention**: For staged contract refactors in this module, add the failing boundary tests first, then map direct symbol usage before editing. Update only the minimum downstream code required to keep the current batch green; defer semantic rewrites to the task that owns them.

## 2026-05-23: Batch-2 extract_evidence refactor exposed hidden stage coupling

**Problem**: Batch 2 changed catalog/special extraction to emit sparse, `raw_source`-only records, but existing validators and tests still assumed stage output was already full-catalog normalized and `source`-grounded. Without tightening those assumptions, the new stages would either drop valid special evidence or give misleading green tests.

**Investigation**: Added failing tests first for `RawSourceNormalizer`, grouped normalization, and variant-centered grouping. Then traced all direct dependencies on `item.source`, global `normalize()`, and full-catalog stage expectations using targeted `rg` across `extract_evidence/` and its tests.

**Root cause**: The original module conflated three phases: LLM extraction shape, normalization/backfill, and source grounding. Batch 2 splits them, so code that implicitly relied on previous phase ordering needed to be made explicit.

**Solution**:
1. Added `RawSourceNormalizer` and moved stage outputs to `raw_source` before any grounding.
2. Updated `SpecialEvidenceValidator` to accept `raw_source` during the pre-grounding phase instead of hard-requiring grounded `source`.
3. Added `GroupAssigner` plus a thin `group_assignment` stage wrapper, with deterministic tie-breaks and local gene inference from block text when explicit gene items are absent.
4. Added `EvidenceItemNormalizer.normalize_grouped()` while keeping legacy `normalize()` intact for older callers and tests.

**Prevention**: When refactoring pipeline phase boundaries, identify every consumer that depends on the old phase ordering before changing runtime shape. Preserve the old API where needed, and add a new method for the new phase semantics instead of overloading one helper with both meanings.

## 2026-05-23: Batch-3 extract_evidence refactor required workflow-level integration, not just local logic

**Problem**: Tasks 7-9 each passed in isolation once their local logic was updated, but the first batch-level verification still failed because workflow and stage integration lagged behind the refactors. The concrete gaps were an old `QualityValidationStage` import in `workflow.py`, the old `SourceGroundingStage.run(document, items)` signature, and legacy tests still expecting pre-refactor chain/grounding semantics.

**Investigation**: Ran each task slice first (`test_source_grounder.py`, `test_chain_builder.py`, `test_quality_validator.py`) and then a combined Batch 3 verification slice. The combined run surfaced integration failures immediately: import drift, stage signature mismatch, and one remaining Ruff failure from a missing `ContentBlock` import in `core.py`.

**Root cause**: The plan refactors three adjacent phases of the same workflow. Local tests proved the new behavior, but the orchestration layer still encoded the old topology and old call signatures. This is a classic failure mode when staged refactors change both data shape and control flow.

**Solution**:
1. Reworked `SourceGrounder` to consume `raw_source`, propagate block metadata, and ground special records separately.
2. Refactored `EvidenceChainBuilder` to build per-group `full` / `partial` / `singleton` chains and attach `special_evidence_ids`.
3. Updated `QualityValidator` to accept chains and special records, and renamed the stage to `QualityGateStage`.
4. Updated `workflow.py` to pass grounded special records into chain assembly and quality gating, and to use the new stage signatures.

**Prevention**: For multi-phase workflow refactors, do not trust isolated task slices alone. After each task-level green run, immediately run one combined “batch integration slice” that includes the touched workflow/stage tests. It catches import drift and signature mismatches before they accumulate.

### Problem 5: zh_functional suspicious char ratio (1 document, LOW)

zh_functional has char ratio 0.58 (translation shorter than source), unusual for zh→en. Possible content truncation.

**Full report**: `/tmp/translation_review_report.md` — per-document table with block counts, char ratios, REDACTED counts, terminology entries, and warnings for all 24 documents.

### Problem 6: es/pt translations completely unchanged + [REDACTED] name-internal insertion

**Root cause analysis**:

1. **es/pt unchanged translations (CRITICAL)**: LLM returned source text unchanged for all 6 es/pt documents. Validation correctly detected failure (`unchanged` / `non_english_output`) but only appended warnings — the result was still persisted via `DocumentPersistenceService.save()`.

2. **[REDACTED] inside names (HIGH)**: `_REDACTED_IN_WORD_RE` regex `(?<=[A-Za-z])\[REDACTED\](?=[A-Za-z])` required a letter on BOTH sides. Pattern "Takayuki [REDACTED]okia" has space before `[REDACTED]`, not a letter — missed by regex.

3. **Empty terminology maps (MEDIUM)**: `_parse_terminology()` had `source.isascii()` filter that rejected all Latin-script source terms. Correct for CJK→en but wrong for es/pt→en where source terms are Latin-script.

**Solutions**:

1. `run_pipeline()` now raises `TranslationError` on critical validation failures (`unchanged`, `non_english_output`, `empty`), preventing persistence of garbage translations. Caller must handle the exception.

2. Broadened `_REDACTED_IN_WORD_RE` to also match `\[REDACTED\](?=[a-z]` — catches space-before-lowercase pattern like `[REDACTED]okia`.

3. `_parse_terminology()` now accepts `source_language` parameter. For CJK languages (zh/ja/ko), keeps non-ASCII filter. For Latin-script languages (es/pt/ru/etc.), accepts ASCII source terms but skips source≈target echo.

**Files changed**:
- `backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/validator.py` — regex fix
- `backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/translator.py` — TranslationError, _parse_terminology language-awareness
- `backend/src/core/cross_lingual_process_and_extract_evidence/workflow.py` — TranslationError import
- `backend/tests/.../test_translator.py` — updated + new test for Latin-script terminology

**Prevention**: Translation validation failures must be treated as hard errors, not soft warnings, when the failure is clearly critical (unchanged output, wrong language). Non-critical warnings (image refs, repetition) remain soft.

## 2026-05-20: Deep translation review — additional findings after second pass

### Problem 7: zh_functional keyword blocks hallucinated with repeated title/abstract (CRITICAL, 1 doc)

Original keywords (古菌, 硫化叶菌, 重组, RadA, stRadC, Hjc — 6 separate blocks) were replaced in the translated output with repeated copies of the full paper title (3×) and abstract opening (2×). Only "Hjc" was correctly translated. This is LLM hallucination on short isolated text blocks — the model filled small keyword slots with surrounding context instead of translating.

**Root cause**: LLM translation of very short isolated text blocks (1-4 CJK chars) is prone to context contamination. The model saw the full title/abstract nearby and repeated them instead of translating the isolated keyword.

**Fix needed**: (a) Add a pre-merge pass for adjacent short keyword blocks before sending to LLM, translating them as a group "古菌；硫化叶菌；重组；RadA；stRadC；Hjc", then splitting after. (b) Add post-translation validation that detects repeated long strings across adjacent blocks.

### Problem 8: ru document only partially translated (CRITICAL, 1 doc)

The Russian document (elibrary_53981733_40074746, TRPV4-associated neuropathies) had page 1 translated (title, abstract, keywords, citation) but ALL body text from "Введение" (Introduction) onward remained in Russian — approximately 99 of 109 blocks untranslated. First-pass review misclassified this as "usable" because char ratio (0.94) didn't flag it.

**Root cause**: The translation pipeline likely processes serially and the LLM call for page 2+ failed silently, leaving subsequent blocks as Russian source text. Same root cause as es/pt but with a single page succeeding.

**Fix needed**: Add per-block or per-page translation success tracking. After translation, verify each block's detected language matches target language (English), not just aggregate char ratio.

### Problem 9: zh bilingual document block duplication (MEDIUM, 3+ docs)

Chinese medical journals often include both Chinese and English versions of title/authors/abstract in the same PDF. The pipeline translates the Chinese blocks AND preserves the pre-existing English blocks, creating redundant copies of the same content (e.g., English title appears twice, English author list appears twice).

**Fix needed**: Add a deduplication pass that detects near-identical adjacent blocks (similarity > 0.9) and removes the duplicate, preferring the translated version (which has consistent terminology) over the original English version (which may have inconsistent terminology).

---

## 2026-05-20: Translation Round 2 fixes — keyword hallucination, per-block lang detection, bilingual dedup

### Fix 1: Keyword merging for short CJK blocks (Problem 7)

**Problem**: LLM fills short 1-4 char CJK keyword blocks with nearby content (title/abstract) instead of translating them.

**Root cause**: Isolated short blocks provide insufficient context for the LLM, causing it to "hallucinate" by repeating nearby long text.

**Fix**: Added `_merge_short_keywords()` preprocessing step that merges adjacent short keyword blocks into a single block joined with `；` before translation. After translation, `_split_merged_keywords()` restores individual translations. The merge only affects adjacent short blocks — long blocks act as barriers.

**Files**: `translator.py` — `_merge_short_keywords`, `_split_merged_keywords`, `_is_short_keyword`, `_KW_MERGE_SEP`; modified `_translate_blocks` to call merge/split.

### Fix 2: Per-block language detection (Problem 8)

**Problem**: Partial translation failures (e.g. ru doc where only page 1 was translated) were not caught by aggregate char ratio checks.

**Root cause**: `validate_translation_output` checks overall text, not per-block. A document with 10% translated blocks could pass if that 10% was long enough.

**Fix**: Added `_check_block_language()` method that uses script-specific regex (Cyrillic for ru, CJK for zh/ja, Hangul for ko) to detect blocks still in source language. Raises `TranslationError` if >40% of text/title blocks remain untranslated. Called in `translate_to_result()` after `_build_translated_blocks()`.

**Files**: `translator.py` — `_check_block_language`, `_CYRILLIC_RE`, `_HIRAGANA_KATAKANA_RE`, `_HANGUL_RE`, `_UNTRANSLATED_BLOCK_RATIO`, `_BLOCK_SOURCE_LANG_THRESHOLD`.

### Fix 3: Bilingual block deduplication (Problem 9)

**Problem**: Bilingual zh documents have adjacent blocks with same content in Chinese and English. After translation, both become English, creating duplicates.

**Root cause**: The pipeline doesn't distinguish between source-language blocks and pre-existing English blocks in bilingual documents.

**Fix**: Added `_deduplicate_bilingual_blocks()` method that detects adjacent text/title blocks with >75% token overlap and removes the duplicate, keeping the longer block (likely the translated one). Called in `translate_to_result()` after `_build_translated_blocks()` and before `_check_block_language()`.

**Files**: `translator.py` — `_deduplicate_bilingual_blocks`, `_DEDUP_SIMILARITY_THRESHOLD`.

### Tests

- `test_round2_fixes.py`: 24 tests covering all 3 fixes (keyword merging: 9, per-block detection: 8, bilingual dedup: 7)
- `test_translator.py`: 21 existing tests — all pass
- `test_e2e_es_pt.py`: 71 existing tests — all pass
- Total: 265 tests pass, 1 skipped (pre-existing DAX-1 dash encoding issue)

## 2026-05-21: Local skill and MCP startup warnings

**Problem**: Codex startup reported 5 skipped skills because `SKILL.md` files lacked YAML frontmatter, and the `time` MCP client failed during startup handshaking.

**Investigation**: Checked the five reported skill files under `/home/yangzs/.cc-switch/skills/` and confirmed each started with a Markdown heading instead of `---`-delimited `name` and `description` frontmatter. Checked `/home/yangzs/.codex/config.toml` and found `time` configured as `npx -y @modelcontextprotocol/server-time`. Running that command returned npm `E404`, confirming the package does not exist in the npm registry. Probed `uvx mcp-server-time --local-timezone=Asia/Shanghai` with a JSON-RPC `initialize` request and got a valid MCP initialize response.

**Root cause**: The skills were missing required metadata, and the `time` MCP server referenced a nonexistent npm package instead of the available Python MCP server package.

**Solution**: Added minimal valid frontmatter to `ts-react`, `rust-dev`, `data-analysis`, `agent-dev`, and `bioinformatics` skills. Updated Codex `time` MCP config to use `uvx mcp-server-time --local-timezone=Asia/Shanghai`.

**Prevention**: Validate skill files for `---`, `name`, and `description` before syncing, and test stdio MCP servers with a direct JSON-RPC `initialize` probe after changing launcher commands.

## 2026-05-21: Dual evidence extraction fixture path and lint cleanup

**Problem**: The first Fabry dual-track e2e test built the fixture path as `<repo>/output/zh/法布雷病1例` instead of `<repo>/backend/output/zh/法布雷病1例`. Ruff also exposed stale unused imports in nearby tests and an invalid `# noqa` directive on a helper that did not return a dict.

**Investigation**: Ran the targeted RED/GREEN test command and inspected the `FileNotFoundError` path. Re-ran Ruff on the extract_evidence source and tests to isolate style issues introduced or exposed by the change.

**Root cause**: The test file's `Path.parents` index was off by one because tests run under `backend/tests/...`. The lint issues were stale imports and an unnecessary noqa comment rather than behavior defects.

**Solution**: Corrected the fixture root to `backend/output/zh/法布雷病1例`, removed stale imports, and removed the invalid noqa.

**Prevention**: For fixture tests under nested test directories, verify `Path(__file__).resolve().parents[...]` with the actual failing path before assuming the repository root. Keep noqa comments tied to real linter codes only.

## 2026-05-21: Real LLM evidence extraction needed JSON-text fallback

**Problem**: The real-LLM Fabry dual-track e2e failed on the local OpenAI-compatible model endpoint. First, the endpoint rejected `response_format=json_schema` with `This response_format type is unavailable now`. After adding fallback for model classes, the catalog stage failed locally before the HTTP call because LangChain could not build `with_structured_output()` for `list[EvidenceItem]`.

**Investigation**: Ran the real e2e with temporary `EVIDENCE_EXTRACTION_*` variables mapped from `backend/.env.local` LLM settings. Read the full stack traces and confirmed two separate failures: provider capability mismatch at the HTTP boundary, and local schema construction mismatch for parametrized list schemas.

**Root cause**: The provider assumed every configured OpenAI-compatible service supports OpenAI strict structured outputs. It also assumed `with_structured_output()` accepts `list[BaseModel]`, but this LangChain/OpenAI path expects a model/tool-like schema rather than a Python parametrized list alias.

**Solution**: Added a provider fallback path that prompts for plain JSON and validates with Pydantic `TypeAdapter`. BaseModel schemas still try strict `json_schema` first; list schemas go directly through JSON-text validation. Added provider regression tests for unsupported response format and list-schema validation.

**Prevention**: For OpenAI-compatible model servers, test both the transport-level structured-output capability and local schema construction behavior. Use `TypeAdapter` when stage outputs are parametrized containers such as `list[EvidenceItem]`.

## 2026-05-21: Extract evidence E2E script exposed config and JSON repair gaps

**Problem**: The first run of `scripts/e2e_extract_evidence.py` failed because `EVIDENCE_EXTRACTION_*` credentials were empty. After sourcing `.env.local`, the script later failed when the JSON-text fallback received invalid LLM JSON: first an illegal backslash escape, then malformed JSON that needed model repair.

**Investigation**: Ran the script against `output/cross_lingual/zh/法布雷病1例` and read the full stack traces. The credential failure came from creating `EvidenceExtractionService` with a cached config built before env mapping. The JSON failures came from fallback parsing in `providers.py`.

**Root cause**: The script assumed evidence extraction env vars were configured directly, while local development commonly has only `LLM_*`. The provider fallback assumed JSON-text output would be syntactically valid after simple fence stripping.

**Solution**: Updated the script to map `LLM_*` or loaded `cfg.llm` values into `EVIDENCE_EXTRACTION_*` inside the process before creating the service and clearing the config cache. Added invalid JSON escape repair and one LLM-based JSON repair retry in the provider fallback, with regression tests.

**Prevention**: E2E scripts that depend on role-specific LLM config should validate or derive that config before constructing services. JSON-text fallback paths need tests for common malformed model output, not only happy-path JSON.

## 2026-05-22: Worktree plan document was written to the main workspace

**Problem**: While implementing extract evidence quality gates in an isolated git worktree, the implementation plan was first created under the main workspace `docs/plans/` instead of the active worktree.

**Investigation**: `git status --short` in the main workspace showed an unexpected untracked plan document. The isolated worktree did not contain that file. The path check confirmed the file existed only under `/data/yangzs/Projects/01_ACMG_Lingua/docs/plans/`.

**Root cause**: The file creation used a relative path while the active tool context was still the main workspace, even though subsequent shell commands were already running in the worktree.

**Solution**: Moved the plan document into the isolated worktree under `docs/active/2026-05-22-extract-evidence-quality-gates.md` and updated the worktree `docs/README.md` index. The main workspace untracked plan file was removed by the move; unrelated main-workspace changes were left untouched.

**Prevention**: After creating or switching to a worktree, use absolute paths or confirm `git status --short` in both main and worktree before the first file edit. Avoid `apply_patch` with relative paths until the target workspace path is explicit.

## 2026-05-22: evidence_map needed JSON mode instead of json_schema

**Problem**: The `evidence_map` stage logged `model does not support json_schema response_format; falling back to JSON text` on some models, even though the stage only needs a simple relevance map and not full schema enforcement.

**Investigation**: Checked the evidence extraction provider, stage wiring, prompts, and the translation pipeline's JSON mode helper. Confirmed `evidence_map` was still using `with_structured_output(..., method="json_schema")`, while the prompt did not provide a concrete JSON example.

**Root cause**: The stage was routed through the stricter structured-output path even though it only needs a JSON object. That forced unsupported models onto the slower fallback path unnecessarily.

**Solution**: Switched `evidence_map` to `json_mode`, added an explicit JSON object example to the prompt, and kept the JSON-text fallback for broader compatibility. Added regression tests for the prompt content, provider method choice, and stage wiring.

**Prevention**: For small JSON-only outputs, prefer JSON mode plus a concrete example prompt. Reserve `json_schema` for stages that actually benefit from schema-level enforcement.

## 2026-05-22: Fabry fixture signature drift exposed test-double mismatch

**Problem**: The real Fabry dual-track e2e failed with `TypeError` because the deterministic test double `FabryFixtureProvider.invoke_structured()` did not accept the new `response_method` keyword used by `EvidenceMapStage`.

**Investigation**: Re-ran the single failing test and confirmed the failure originated at the stage/provider boundary before any extraction logic executed.

**Root cause**: The stage interface gained a `response_method` argument, but the fixture provider stayed on the older signature. The review also surfaced a permissive substring fallback in `_source_is_traceable` and missing regression coverage for ambiguous chains and `G.*` case-control filtering.

**Solution**: Added the `response_method` parameter to the fixture provider, tightened the short-snippet traceability fallback, added regression tests for ambiguous-source chain suppression and `G.*` case-control filtering, and refreshed the module README/progress counts.

**Prevention**: When a stage API changes, update deterministic test doubles in the same patch set. Add a regression test at the boundary where the new parameter is consumed so fixture drift fails immediately.

## 2026-05-22: Autostash merge conflict in progress.txt

**Problem**: Fast-forwarding the extract-evidence quality gate work into `dev` left an autostash conflict in `progress.txt`, while unrelated benchmark edits remained in the working tree.

**Investigation**: Checked `git status`, the conflict markers, and both conflict sides to confirm that the branch version held the extract-evidence progress entries and the stash side held the `extract-evidence-output-review` note.

**Root cause**: `git merge --autostash` reapplied a tracked progress update on top of another tracked progress update, so Git could not append the entries automatically.

**Solution**: Resolved `progress.txt` by keeping both sets of entries, added a merge-completion log line, and left the benchmark edits untouched so the workspace still reflects the user's local changes.

**Prevention**: When merging with autostash, inspect `progress.txt` explicitly before dropping the stash and treat tracked log files as likely conflict points.

## 2026-05-22: extract_evidence quality gates over-filtered grounded evidence

**Problem**: The Fabry regression run under `backend/output/extract_evidence/法布雷病1例/20260522_154916` dropped `FOUND` counts, marked grounded Chinese snippets as `source_invalid`, turned translated `B.disease_diagnosis` into `ambiguous`, and filtered all special evidence records to zero.

**Investigation**: Compared `20260522_154916` against the earlier `20260522_113744` output, then traced the behavior back to the `2e1014a5` quality-gate patch. Reproduced the regressions with focused tests for CJK OCR spacing, table-backed grounding, repeated title disease mentions, zero-offset special-evidence snippets, non-`G.*` case-control records, and human-review reason layering.

**Root cause**:
1. `SourceGrounder` only performed literal substring matching, so OCR-spaced CJK snippets like `基 因 变 异` failed even when the normalized text existed in-document.
2. Table-backed sources were treated as missing text because grounding never fell back to caption/body-like table text in `formatted_text`.
3. Repeated disease-title mentions always became `AMBIGUOUS`; there was no field-specific candidate preference for title-like `B.disease_diagnosis`.
4. `SpecialEvidenceValidator` rejected zero-offset but traceable snippets and hard-blocked all non-`G.*` case-control records, which removed authority/discussion evidence that the earlier output had preserved.
5. Review output was only flattened into `human_review_reasons`, which made downstream interpretation noisy.

**Solution**: Added normalized grounding for OCR-spaced CJK snippets, table-aware fallback matching, and nearest-candidate preference for `B.disease_diagnosis`. Relaxed special-evidence validation to accept traceable zero-offset snippets and traceable non-`G.*` case-control discussion evidence while still rejecting `[REDACTED]` statistical records. Added `human_review_by_category` alongside the existing flat reason list and propagated it into the E2E summary output. Verified with targeted extract-evidence tests, workflow/contract regression tests, and Ruff.

**Prevention**: When tightening quality gates, always replay a real fixture diff against the immediately previous good run and add tests for the exact false-negative patterns before shipping the stricter logic. For grounding code, treat OCR-spaced CJK text, repeated title/body mentions, and table-derived evidence as first-class search cases rather than fallback edge cases.

## 2026-05-22: prompt snippet drift and table-path grounding needed separate handling

**Problem**: The new Fabry log showed a smaller, more specific regression surface than the previous run: SOURCE_INVALIDs came from snippet drift in LLM-generated source text, while table-backed evidence was being collapsed into OCR-style failures even when the data existed.

**Investigation**: Re-read `backend/output/extract_evidence/法布雷病1例/20260522_183101` and compared the surviving false negatives against the code path in `SourceGrounder` and the prompt builders. The residual failures clustered around three behaviors: deleted/reworded source snippets, ellipsis-spliced snippets, and table misses being treated as image/OCR loss.

**Root cause**:
1. The prompt did not explicitly require `source.text_snippet` to be a verbatim continuous substring with punctuation copied exactly.
2. `SourceGrounder` had no hard ellipsis rejection, so `...`-bridged snippets could survive into grounding.
3. Table-backed misses were still being labeled as OCR gaps even when the data path was obviously table-specific, which hid the distinction between a text-extraction limit and a table-grounding limit.

**Solution**: Added strict verbatim and punctuation-copy rules to both catalog and special-evidence prompts, hard-rejected ellipsis snippets as `SOURCE_INVALID`, introduced `TABLE_UNGROUNDED` for table-path misses, and threaded that status into validation and E2E summaries. Added regression tests for prompt text, ellipsis invalidation, and table-path handling, then verified the targeted suite and Ruff.

**Prevention**: When the failure class is “snippet drift,” make the prompt rules machine-checkable and exact. When the failure class is “data exists but the path is wrong,” represent that explicitly with its own status instead of reusing OCR-gap semantics.

## 2026-05-22: special_evidence JSON text fallback was too fragile

**Problem**: Running `uv run scripts/e2e_extract_evidence.py` on the Fabry fixture aborted inside the translated track with `pydantic_core.ValidationError: Invalid JSON: invalid escape`, originating from the `special_evidence` stage.

**Investigation**: Traced the exception to the provider's JSON-text fallback path. The stage was still asking for a bare `list[SpecialEvidenceRecord]`, which forced a brittle text-only repair path. The model output contained backslashes that the fallback repair path could not fully normalize before `validate_json()`.

**Root cause**: `special_evidence` was using the least stable structured-output shape for a stage that already emits complex natural-language descriptions. A bare list schema plus text fallback made the pipeline fragile to escape sequences in the model response.

**Solution**: Wrapped the output in a Pydantic `SpecialEvidenceResponse` with a `records` field and forced `json_mode` for the stage. That keeps the response shape stable, avoids the brittle bare-list text fallback, and still preserves the post-parse validator filtering. Added tests at the provider and stage boundary and verified the full targeted suite plus Ruff.

**Prevention**: For any stage that can emit long prose, prefer a wrapper object over a naked list and use the response mode with the simplest stable contract. Keep brittle repair paths behind a typed envelope, not directly on the user-facing payload shape.

## 2026-05-22: inferred case_count without source was blocking the gate

**Problem**: The translated v3 output had `B.case_count` marked `FOUND` with `source=null`, which triggered a hard `missing_source` error in quality validation and blocked the translated track even though the value was only an inferred case count from article structure.

**Investigation**: Rechecked the latest Fabry output and confirmed the item was an inference-only count, not a traceable excerpt. The failure was localized to the gate: the item should remain visible for review, but it should not fail the score gate the way a true source-bearing `FOUND` item would.

**Root cause**: The quality path treated every `FOUND` item without a source as structurally invalid, even for fields that can reasonably be inferred from document structure. That made `B.case_count` a gate blocker instead of a reviewable inference.

**Solution**: Added a narrow exception for `B.case_count` so it is downgraded into non-blocking handling without changing the broader `FOUND` semantics for other fields. Kept review visibility via the human-review reason list and verified the targeted extract-evidence suite plus Ruff.

**Prevention**: Separate “traceable evidence” from “inference from document structure” in the contract or prompt design. Fields that can be inferred should not be forced through the same source requirements as verbatim evidence spans.

## 2026-05-25: benchmark analyze 增加 LLM PDF 领域分类时的执行路径问题

**Problem**: 在执行 `benchmark.py analyze --llm-classify` 时，工具链有时不会按预期工作目录执行命令，导致结果检查和落盘确认出现偏差。

**Investigation**: 对比脚本输出与 `report.json` 内容，发现命令执行状态与文件落盘状态不一致。进一步通过绝对路径 + `PYTHONPATH` 方式执行后，`medical_domain` 与 `analysis_summary` 正常写入。

**Root cause**: 终端调用在部分场景下会简化命令并丢失 `cd ... &&` 的上下文假设，脚本实际运行目录与预期不一致。

**Solution**: 对 backend 脚本统一采用绝对路径调用，并显式设置 `PYTHONPATH=/home/yangzs/Projects/01_ACMG_Lingua/backend`；结果校验以文件内容为准（检查 `medical_domain`、`analysis_summary` 字段）。

**Prevention**: 后续需要依赖相对导入路径的脚本执行时，默认使用绝对路径 + 显式 `PYTHONPATH`，并在任务结束前做一次文件级落盘核验。

## 2026-05-25: Phase 3 E2E script needs document-root refresh path and sync/async helper compatibility

**Problem**: 实现阶段三 E2E 脚本时，第一次测试暴露了两个问题：`--refresh-upstream` 把阶段二刷新输出写到了错误层级；同时，测试里把辅助函数 monkeypatch 成同步函数后，脚本直接 `await` 会报 `NoneType can't be used in 'await' expression`。

**Investigation**: 先用 TDD 为 `backend/scripts/e2e_standardize_entities.py` 写了脚本级测试，覆盖默认输入目录、可选刷新上游、可选术语导入和输出摘要。红灯阶段显示新脚本缺失；首版实现后，测试进一步定位到刷新目录和 sync/async helper 兼容性两个边界问题。

**Root cause**:
1. `run_extract_evidence()` 会按 `output_dir / document_id / run_id` 落盘；如果把刷新目标目录设成 `.../extract_evidence/<doc>`，实际会多嵌一层 `<doc>/<doc>/<run>`。
2. 脚本内部默认 helper 是 async，但测试替身为了简化断言使用了同步 lambda，调用方对 helper 返回值形态做了过强假设。

**Solution**:
1. 刷新上游时把目标目录改为 `extract_evidence_dir.parent.parent`，即 `.../extract_evidence/` 文档根的上一级，再使用返回的 `saved_dir` 作为真实输入。
2. 增加 `_maybe_await()`，对辅助钩子统一兼容 sync/async 两种返回值。
3. 为脚本补充 targeted pytest + Ruff 校验，并把真实运行阻塞点单独核验：当前本地 PostgreSQL `127.0.0.1:5432` 未启动，Docker Socket 也不可用，因此未能完成真实落库 smoke run。

**Prevention**:
1. 复用已有 E2E 脚本时，先核对它的最终落盘路径，不要只按参数名猜输出层级。
2. 对脚本内部可 monkeypatch 的 helper，调用侧默认做 sync/async 双兼容，降低测试替身耦合。
3. 宣称“真实 E2E 已跑通”之前，先单独验证基础设施可用性：LLM 环境变量、数据库连通性、容器运行权限。

## 2026-05-26: FAST_LLM / REASONING_LLM naming migration needs compatibility at config boundary

**Problem**: 项目新的 `.env.local` 约定把通用模型拆成 `FAST_LLM_*` 和 `REASONING_LLM_*` 两组，但代码仍主要读取旧的 `LLM_*` / `ARBITRATION_*`（已改为 reasoning 命名）。这会导致配置文件明明已经更新，运行时代码却继续拿到空值或错误模型分层。

**Investigation**: 先直接验证 `Settings()` 的实际解析结果，再补最小红灯测试，覆盖两类行为：`FAST_LLM_* -> cfg.llm`、`REASONING_LLM_* -> cfg.reasoning`，以及 `scripts/e2e_extract_evidence.py` 中强模型不应再回落到快速模型。测试先按预期失败，确认问题在配置兼容层和脚本映射层，而不是使用方。

**Root cause**:
1. `pydantic-settings` 只会自动填充已声明的字段；新增前缀没有对应 flat fields，自然不会进入 `Settings`。
2. 现有代码把“默认模型”和“强模型”绑定到旧命名约定，`extract_evidence` 的 `STRONG` tier 仍错误映射到 `LLM_MODEL`。

**Solution**:
1. 在 `src/core/config.py` 新增 `fast_llm_*` 和 `reasoning_llm_*` flat fields。
2. 保持调用面不变：`cfg.llm` 继续代表快速模型，`cfg.reasoning` 继续代表推理模型，但在 `_build_nested()` 中优先取 `FAST_LLM_*` / `REASONING_LLM_*`，旧 `LLM_*` / `ARBITRATION_*` 仅作兼容回退。
3. 更新 `scripts/e2e_extract_evidence.py::_ensure_evidence_env_from_llm()`，让 `FAST/ STANDARD` tier 走快速模型，`STRONG` tier 优先走推理模型，再回退到旧变量或快速模型。
4. 只用受影响范围做 fresh verification，避免把无关工作区改动混进结论。

**Prevention**:
1. 配置命名迁移时，先在配置边界做兼容，再改调用方；不要要求全仓库一次性切换字段名。
2. 模型分层至少要有一条脚本级回归测试，明确哪个 tier 对应哪个 env/source。
3. 验证配置问题时，区分 `os.environ` 和 `Settings()` 解析结果；前者没导出，不代表 `.env.local` 没生效。

## 2026-05-26: Terminology import root-path bug was isolated to HGNC loader wiring

**Problem**: 真实执行 `uv run python ../scripts/import_terminology.py --terminology-root ../database/terminology_database ...` 时，迁移已成功，但术语导入在 HGNC 阶段直接报 `FileNotFoundError`，路径错误指向 `../database/terminology_database/hgnc_complete_set.txt`。

**Investigation**: 对照 `database/terminology_database/` 实际目录结构检查后确认，只有 HGNC 数据放在 `hgnc/hgnc_complete_set.txt` 子目录下；OMIM/HPO/ClinGen/ClinVar 的 loader 都已经按子目录解析。补了一条红灯测试，把 facade 的 HGNC 路径期望固定为 `terminology_root / "hgnc" / "hgnc_complete_set.txt"`，测试先按预期失败，再修实现。

**Root cause**: `src/core/standardize_entities_and_align_knowledge/api.py::_load_import_batches()` 对 HGNC 这一路单独写错了路径，把它当成了术语根目录下的直文件，而不是 `hgnc/` 子目录内文件。

**Solution**: 将 HGNC loader 路径修正为 `source_root / "hgnc" / "hgnc_complete_set.txt"`，并用 targeted pytest + Ruff 验证。

**Prevention**:
1. facade 层拼接数据根目录时，所有 source 的路径规则都要有测试覆盖，避免只有某一路“手写特例”漂移。
2. 对真实数据导入链路，先用 `find database/terminology_database -maxdepth 2 -type f` 校对物理布局，再写 loader 入口路径。

## 2026-05-26: Long-running terminology import needs explicit progress telemetry

**Problem**: 真实执行 `uv run python ../scripts/import_terminology.py ...` 时，命令可能运行很久，但几乎没有任何进度反馈，使用者无法判断当前是在解析哪一个 source、是否已经开始写库、还是卡住了。

**Investigation**: 检查 CLI 和 facade 后确认，现有实现只在可选 embedding 阶段打日志，核心术语导入链路没有 source 级别可观察性。先补了一条最小测试保证 facade 仍按 batch 顺序写库，再在 CLI 和 facade 两层加日志而不改变导入行为。

**Root cause**: 导入流程把“解析所有 batch”和“逐 batch 写库”都封装在 facade 内，但没有暴露任何中间状态；CLI 入口也没有统一 logger 配置和总耗时统计。

**Solution**:
1. 在 `import_terminology()` facade 中增加日志：
   - 导入开始（root/version/sources）
   - 所有 batch 解析完成后的总计数（entries/aliases/relationships）
   - 每个 batch 的开始/结束导入日志
   - transaction commit 完成
   - 总耗时
2. 在 `scripts/import_terminology.py` 里统一 logger 输出格式，并打印 CLI 请求摘要、embedding 阶段起止和总耗时。
3. 用 targeted pytest + Ruff 验证，保证日志增强没有改变导入语义。

**Prevention**:
1. 对任何可能运行超过几十秒的数据导入脚本，默认加入 source 级别进度日志和总耗时。
2. 观测点要放在“解析完成”和“写库完成”两个边界上，这样用户能区分 CPU/IO/DB 三类瓶颈。

## 2026-05-26: ClinVar “streamed parser” still needs true streaming all the way to the DB boundary

**Problem**: Phase 3 文档里原本写着 “ClinVar import is streamed row-by-row”，但真实实现虽然逐行读取 TSV，最后还是把 3.7G / 898 万行数据累成一个巨大的 `ImportBatch`，然后再交给逐条 ORM upsert。对大文件来说，这会同时拖垮内存占用和数据库吞吐。

**Investigation**: 核查后确认性能瓶颈不在 CPU（i7-14700 / 28 threads 远够用），而在导入结构：
1. parser 端把全部 ClinVar 结果聚合到内存；
2. repository 端对每条 entry/alias/relationship 逐条 `SELECT` + `add`。
先补红灯测试，要求 ClinVar 能按 chunk 产出多个小 `ImportBatch`，再在 facade 里把 ClinVar 从普通 `_load_import_batches()` 路径中剥离，改为专门的 streaming import path。

**Root cause**: 之前的“streamed”只覆盖了文件读取阶段，没有贯通到 API facade 和 DB 写入边界；真正的内存峰值和慢查询都发生在后半段。

**Solution**:
1. 新增 `iter_clinvar_batches(path, version, chunk_size)`，按 chunk 产出有界 `ImportBatch`。
2. `import_terminology()` facade 对 `ClinVar` 单独走 `_import_clinvar_stream(...)`，不再把它塞进普通的 monolithic batch 列表。
3. 保留 `parse_clinvar_rows()` 兼容接口，但不再作为真实大文件导入主路径。
4. 用 targeted pytest + Ruff 验证 importer/API 行为。

**Current status**: 这一步已经消除了 ClinVar 导入的最大内存炸点，但 DB 侧仍然是逐条 ORM upsert，吞吐瓶颈还在。下一步若继续追求“最大性能”，必须进入 bulk SQL / staging table 路线。

**Prevention**:
1. “streaming”要定义到系统边界，而不是只看文件读取阶段。
2. 面对百万级以上行数时，默认先审视“是否有 monolithic in-memory aggregate”与“是否逐条 DB round-trip”。

## 2026-05-26: 本地 Phase 3 实测被两个基础问题同时掩盖了

**Problem**: 用户已经在 `backend/.env.local` 配好了 FAST/REASONING LLM 与 PostgreSQL，但本地运行时仍然出现“LLM 变量未设置”和 `127.0.0.1:5432 connection refused`。同时，术语导入 bulk 路径虽然提速了 entry upsert，却把 `ClinGen` 这类依赖已存在 HGNC alias 的 relationship 解析静默丢掉了。

**Investigation**:
1. 直接在 `backend/` 目录实例化 `Settings()`，确认 `FAST_LLM_*`、`REASONING_LLM_*` 和 `POSTGRES_*` 实际都能读到；说明不是字段名不兼容，而是 env 文件定位与运行目录耦合。
2. 回看 `SettingsConfigDict(env_file=(\".env.local\", \".env\"))`，发现它按当前工作目录找文件；从仓库根或其他目录启动脚本时，会误判成“变量未设置”。
3. 给 repository 补红灯测试后确认，`RETURNING`-based bulk path 只拿到了本 batch 新写入/更新的 `external_id -> entry_id` 映射，没有继续解析关系里通过 alias 引用的已有实体，导致 `ClinGen` dosage / gene-disease 关系在 bulk 模式下会漏写。

**Root cause**:
1. 配置层默认 env-file 解析依赖 cwd，而不是仓库/服务的稳定绝对路径。
2. bulk upsert 优化时只关注 entry insert 吞吐，漏掉了“关系目标可能来自历史已导入实体而非当前 batch”的数据依赖。

**Solution**:
1. 将 `src/core/config.py` 的默认 `env_file` 改为仓库根和 `backend/` 下的绝对路径列表，彻底去掉 cwd 依赖。
2. 在 Phase 3 repository 中：
   - 支持通过 asyncpg `copy_records_to_table` + temp staging table 导入 entries/aliases/relationships；
   - 在 bulk path 中补齐 `external_id` 再查询和 alias reference 解析，保证 `ClinGen` 等关系仍能连到已存在 HGNC 实体。
3. 用定向 pytest + Ruff 验证配置加载、COPY 路径和 alias relationship 回归。

**Prevention**:
1. 所有需要 `.env.local` 的后端脚本都应使用与 cwd 无关的绝对 env-file 定位。
2. 做 bulk/import 优化时，除了吞吐，还必须列出“本批新数据”“库内历史数据”“alias/外键引用”三类引用来源，并分别验证。

## 2026-05-26: 真实 Phase 3 E2E 会把“测试里没覆盖的 schema 漂移”和“真实数据脏点”一次性暴露出来

**Problem**: 用 `backend/output/extract_evidence/法布雷病1例/latest` 做真实 Phase 3 E2E 时，先后暴露出一串只在真实环境里才会触发的问题：
1. OMIM / ClinGen 文件有前置说明行，parser 返回空 batch。
2. COPY 导入对 HGNC alias 和 ClinGen relationship 的批内重复键会触发 `ON CONFLICT ... cannot affect row a second time`。
3. 本地数据库缺少 `terminology_relationships` 唯一约束，导致关系 upsert 失败。
4. Alembic revision id 超过 32 字符，迁移更新 `alembic_version` 时直接截断报错。
5. Phase 3 E2E 在持久化 `run_evidence_items` 前没有先写 `source_documents` / `processing_runs`，外键直接失败。
6. 本地 model-server 未启动时，semantic matching 不该让整个 E2E 崩掉。

**Investigation**:
1. 先用真实 PostgreSQL 逐步跑 `import_terminology.py`，把错误从“连接失败”缩到具体的 SQL/constraint/cardinality/fk 问题。
2. 对每个真实错误先补红灯测试，再修：
   - importer 测试覆盖 OMIM/ClinGen preamble/header 变体；
   - repository 测试覆盖 alias/relationship COPY 去重；
   - matcher/similarity 测试覆盖 semantic 服务故障降级；
   - alembic 测试覆盖关系唯一约束和 revision 链。
3. 每次只推进一个真实阻塞点，避免把导入、迁移、E2E 三条链路混在一起排查。

**Root cause**:
1. 之前大多是 stub / fake session 测试，覆盖不到真实文件格式、真实约束缺失和真实外键依赖。
2. COPY/staging 优化只考虑了吞吐，没有同时考虑“批内重复键”。
3. schema 演进和本地库实际状态有漂移，尤其是唯一约束与 revision id 长度。
4. E2E 脚本默认假设上游父表和模型服务都已经可用。

**Solution**:
1. importer：
   - 支持 OMIM `#` 注释前言后再找真实 header；
   - 支持 ClinGen CSV 前置说明行和两套 header 变体。
2. repository：
   - COPY entries/aliases/relationships 前按各自冲突键批内去重；
   - 关系 upsert 按列冲突定义工作；
   - 真实 E2E 前自动补齐 `SourceDocument` / `ProcessingRun` 父记录。
3. migration：
   - 新增补关系唯一约束的增量 migration；
   - 将新增 revision id 缩短到 32 字符以内，避免 `alembic_version` 截断。
4. matching：
   - semantic provider / repository / rerank 的基础设施错误统一包装成 `SemanticMatchServiceError`；
   - Hybrid matcher 统一降级为 `UNMAPPED`，真实 E2E 不再因本地 model-server 未启动而中断。

**Outcome**:
真实 Phase 3 E2E 已跑通，输出目录：
`backend/output/standardize_entities/法布雷病1例/latest-real`

关键结果：
- `match_count=13`
- `standardized_count=5`
- `ambiguous_count=0`
- `unmapped_count=8`

**Prevention**:
1. 任何“性能优化”只要切到 raw SQL/COPY，就必须补“真实批内重复键”测试。
2. 任何 E2E 脚本只要会落库，就必须显式负责父表存在性，而不是依赖外部预置状态。
3. 新增 Alembic revision id 时，先检查是否超过本库 `alembic_version.version_num` 长度限制。
4. 真库实测要尽早做，不能等到所有单测都绿了再第一次碰真实数据。

## 2026-05-26: ClinVar 接入如果只“导进去”还不够，必须同时处理别名歧义和超大事务

**Problem**: 把 ClinVar 接入真实导入链路后，第一次真实导入虽然能跑很久，但在提交阶段因为单事务持有过多锁而触发 PostgreSQL `out of shared memory / max_locks_per_transaction`。即使导入成功，`p.R227X` 也只是从 `unmapped` 变成 `ambiguous`，因为 ClinVar 中同一 protein-short alias 会命中多个基因背景不同的变异。

**Investigation**:
1. 对 `variant_summary.core.tsv` 抽样统计后确认：
   - 大量 `VariationID` 重复，但在核心字段裁剪后多数是完全重复行；
   - 重复行在文件中是连续出现的，可以在预处理阶段流式去重。
2. 用真实 Fabry 案例验证后确认：
   - 接入 ClinVar 后 `p.R227X` 已能命中多个 `protein_short` alias；
   - 真正缺的是用链上的 `gene=GLA` 进一步消歧。
3. 继续真实导入 ClinVar 时，发现 400+ chunk 虽然逐 chunk upsert，但仍放在一个外层事务里，commit 时集中爆掉共享内存。

**Root cause**:
1. ClinVar 数据量过大，不能沿用“整个源一笔事务提交”的策略。
2. 变异短写法（如 `p.R227X`）本身跨基因可重名，只靠 alias 文本无法唯一命中。
3. model-server provider 的 base URL 归一化不严谨，`/v1` 会被重复拼接成 `/v1/v1/...`。

**Solution**:
1. ClinVar 预处理：
   - 只保留核心字段；
   - 过滤不可导入 review status；
   - 去掉连续完全重复行；
   - 真实 core 文件从 3.7G 原始 TSV 收缩到约 699M。
2. ClinVar 导入：
   - 改为每个 chunk 自己 commit，不再让 400+ chunk 共用一个巨型事务。
3. ClinVar variant alias：
   - 从 `p.Arg227Ter` 派生 `p.R227X` 这类 one-letter protein alias；
   - precise variant matcher 再用 `candidate.metadata["gene_symbol"]` 过滤同 alias 的跨基因候选。
4. semantic provider：
   - 统一 base URL 归一化，避免 `/v1/v1/embeddings` 这类错误路径。

**Outcome**:
Fabry 真实 Phase 3 E2E 结果变化：
- 初始：`standardized=5, ambiguous=0, unmapped=8`
- 仅接 ClinVar：`standardized=5, ambiguous=1, unmapped=7`
- 加入 gene-context 消歧后：`standardized=6, ambiguous=0`

关键收益是：
- `p.R227X` 最终标准化为 `ClinVarVariation:10733`
- 对应展示名：`NM_000169.3(GLA):c.679C>T (p.Arg227Ter)`

**Prevention**:
1. 超大参考库接入时，预处理和导入事务策略必须一起设计，不能只做字段裁剪。
2. 变异 alias 只要存在跨基因重名，就必须引入 gene/transcript context 参与精确匹配。
3. 对 provider base URL 的 `/v1` 归一化要写成测试，不能靠运行时日志兜底。

## 2026-05-26: 审查产物时也必须遵守 Python 只走 uv 的规则

**Problem**: 审查 `backend/output/standardize_entities/法布雷病1例/latest-real-clinvar` 时，曾用 `python -m json.tool` 临时查看 JSON。虽然只是只读检查，但仍违反了本项目“Python 操作必须通过 `uv`”的依赖/环境规则。

**Investigation**:
1. 该操作发生在快速查看 JSON 内容阶段，本可直接使用 `jq`，无需启动 Python。
2. 后续数据库查询已改为 `uv run python`，符合项目约定。

**Root cause**: 把“只读 JSON 格式化”误当成普通 shell 查看操作，忽略了项目对 Python 命令入口的硬性约束。

**Solution**: 后续 JSON 查看优先使用 `jq`；确需 Python 时统一使用 `uv run python`，并从 `backend/` 或稳定项目路径执行。

**Prevention**: 在本仓库中执行任何 `python` 前先做一次入口检查：能用 `jq`/shell 工具解决则不用 Python；必须用 Python 时命令必须以 `uv run python` 开头。

## 2026-05-26: 审查“已完成”实现时必须重新跑完整目标测试

**Problem**: 一次 Phase 3 修复总结声称“100 Phase 3 tests pass”，但重新运行目标套件时先暴露出新加的 async 测试没有 `@pytest.mark.asyncio`，补上标记后又暴露生产代码缺少 `TerminologyEmbeddingIndexer.build(entity_types=..., source_dbs=...)` 参数支持。同时，混合导入 `hgnc + clinvar` 时因为 `clinvar` 分支跳过最终 `session.commit()`，在 ClinVar stream 被 mock、为空或首 chunk 前失败时，非 ClinVar batch 会停留在未提交事务里。

**Investigation**:
1. 先跑完整 Phase 3 目标套件，确认失败是 `test_similarity_indexer.py::test_embedding_indexer_can_filter_entity_types_and_sources`。
2. 与同目录其他 async 测试对比，发现缺少 `@pytest.mark.asyncio` 是第一层问题。
3. 加上标记后重新运行，真实错误变为 `TerminologyEmbeddingIndexer.build()` 不接受 `entity_types` / `source_dbs`。
4. 审查 `import_terminology()` 事务流时发现：`clinvar` 被选中后只依赖 `_import_clinvar_stream()` 的 chunk commit，外层预加载批次没有最终 commit。

**Root cause**:
1. 新测试没有被正确标记，导致 pytest 没有真正执行 async 断言路径。
2. 测试期望的 indexer 过滤能力没有落到生产实现。
3. 为解决 ClinVar 大事务引入 chunk commit 时，把“ClinVar chunk 提交”和“其他 source batch 最终提交”混为一谈。

**Solution**:
1. 给新 async 测试加 `@pytest.mark.asyncio`。
2. 给 `TerminologyEmbeddingIndexer.build()` 增加 `entity_types` 和 `source_dbs` 过滤参数，并同时在 SQL 查询和 fake-session 结果上保持过滤语义。
3. `import_terminology()` 无论是否包含 ClinVar，最后都执行一次 `session.commit()`，提交外层仍未提交的非 ClinVar batch。
4. 将已完成的计划文档归档到 `docs/archive/plans/` 并更新 `docs/README.md`。

**Prevention**:
1. 审查他人“测试已通过”的总结时，必须自己重跑覆盖目标，而不是采信摘要。
2. 新增 async 测试后必须确认 pytest 真正执行 coroutine，而不是被插件错误拦截。
3. 任何分块提交优化都要单独检查混合 source、空 stream、首 chunk 失败三种事务边界。

## 2026-05-27: model-server embedding_max_model_len 配置修复与进程管理

**Problem**: Phase 3 E2E 在语义层 (semantic) 执行时出现 embedding 接口 500 错误，导致 `水肿`/`蛋白尿`/`心律失常` 等 phenotype 无法通过 pgvector 语义匹配标准化。

**Investigation**:
1. 先确认 vllm.LLM 的 `max_model_len` 参数支持，以及 model-server 的装配入口。
2. 补测试锁死配置链：`test_config.py` 验证默认值 32768 和 env 覆盖 4096；`test_embedding_service.py` 验证装配时参数透传；`test_main_wiring.py` 验证 cfg → service 整条链路。
3. 修改 `app/config.py` 增加 `embedding_max_model_len: int = 32768`，`app/services/embedding.py` 装配时透传 `max_model_len=cfg.embedding_max_model_len`。
4. 本地 `.env.local` 添加 `EMBEDDING_MAX_MODEL_LEN=4096` 降低显存占用。
5. 测试被本地 .env 污染：将默认值测试的 `_env_file=None` 避免环境影响。
6. 服务进程残留问题：`pkill -f model-server` 误杀当前 shell，改用 `lsof -ti:8001 | xargs -r kill` 精准清理。
7. 前台启动验证配置生效：`uv run python main.py` 确认无启动错误。

**Root cause**:
1. vllm 初始化时默认 `max_model_len` 过大，本地显存不足导致加载失败。
2. 配置项未在 config 层声明，无法通过 env 注入覆盖。
3. 进程清理命令过于宽泛，导致重启时端口仍被旧进程占用。

**Solution**:
1. config 层增加 `embedding_max_model_len`，默认 32768（云端），本地通过 env 覆盖为 4096。
2. EmbeddingService 装配时显式透传 `max_model_len` 参数。
3. 测试使用 `_env_file=None` 隔离环境变量污染。
4. 进程清理改用 `lsof -ti:8001` 精准定位 + kill。
5. 重启后验证 `/health`、`/v1/embeddings`、`/v1/rerank` 均返回 200。

**Result**:
- Phase 3 E2E `latest-real-semantic-stable` 稳定跑完，无 embedding 500 错误。
- 标准化结果：`match=18, standardized=7, ambiguous=1, unmapped=10`，与 embedfix 版本一致，无回归。
- 7 项成功标准化：
  - gene: `GLA` → HGNC:4296
  - disease: `法布雷病`/`Fabry disease` → OMIM:301500
  - variant: `p.R227X` → ClinVarVariation:10733
  - phenotype: `Edema`/`Proteinuria`/`Arrhythmia` → HP:0000969/HP:0000093/HP:0011675

**Prevention**:
1. vllm 类模型的 `max_model_len` 必须在 config 层暴露为可配置项，避免硬编码。
2. 测试默认值验证必须 `_env_file=None` 隔离本地 .env 污染。
3. 服务进程清理必须精准定位端口占用 PID，避免 `pkill -f` 误伤。
4. 重启服务后必须先验证基础接口 (`/health`, `/v1/*`) 再跑完整 E2E，避免在异常进程状态下浪费调试时间。

## 2026-05-27: Backend/database audit found stale DAO tests and collection drift

**Problem**: During backend/database review, `uv run pytest tests/dao/test_vector_repo.py -q` failed all 4 tests, and repo-wide `uv run pytest -q --maxfail=1` failed during collection with a `test_config` import mismatch.

**Investigation**: Compared `src.dao.vector_repo.VectorRepository` with `src.dao.models.TerminologyEmbedding` and the pgvector migration. The ORM/migration expose `embedding_text`, `embedding_text_hash`, and `embedding_model`; the stale DAO repository and its tests still reference `source_text` and `model_version`. For collection, both `backend/tests/core/test_config.py` and `backend/services/model-server/tests/test_config.py` are collected as top-level `test_config` modules because most test directories are not packages.

**Root cause**: Phase 3 pgvector schema evolution left the older shared `src/dao/vector_repo.py` path and tests behind while active Phase 3 code moved to `standardize_entities_and_align_knowledge/similarity_match/repositories.py`. The pytest import mismatch is a test package isolation issue, not a business-code failure.

**Solution**: Not remediated in this audit pass. Recommended fixes are to either remove/replace the stale `VectorRepository` with the active typed pgvector repository or align it to the current `TerminologyEmbedding` schema, and to package or rename duplicate `test_config.py` modules so repo-wide pytest collection is stable.

**Prevention**: When schema fields are renamed, search all repositories and tests for old field names, not only the active feature path. Add a repo-wide pytest collection check after introducing service-local tests with common basenames.

## 2026-05-29: Pipeline Orchestrator v5 — Implementation Lessons

**Problem**: LangGraph async/sync API mismatch caused `TypeError: No synchronous function provided`.

**Key corrections**:
1. LangGraph async node functions require `ainvoke()`, not `invoke()` — sync `invoke()` doesn't support async node functions.
2. Mock `AsyncMock.side_effect` with sync lambdas returns unawaited coroutines — use `async def` for side effects that call async operations.
3. Mock adapters returning the same state object for all phases causes incorrect assertions — each phase needs its own state copy.
4. `datetime.fromisoformat(datetime.now().isoformat())` is wasteful — use `datetime.now()` directly.
5. Mid-function imports inside `try` blocks mask `ImportError` as `PermanentPhaseError` — move contract imports to module level.

**Prevention**: When using LangGraph, always match API to node function type: async nodes → `ainvoke()`, sync nodes → `invoke()`.

## Architecture Cleanup (2026-05-29)

### Problem
API routes (`src/api/v1/`) directly instantiated core services, bypassing the `agents` layer.
`deps.py` and `main.py` each created independent SQLAlchemy engines (dual connection pools).

### Resolution
1. Extracted engine/session_factory creation into `src/api/wiring.py` as single source of truth.
2. Created `Phase4ServiceFactory` in `src/agents/` so Phase 4 API routes delegate through agents layer.
3. Refactored `EntityStandardizationService.__init__` to not take session — session is now a method parameter.
4. Merged `state_persistence.py` and `state_persistence_factory.py` into one file with two classes.

### Prevention
- New API routes MUST NOT import from `src/core/` service modules directly.
- New service facades MUST NOT require `AsyncSession` in `__init__` — pass it as method parameter or use factory.
- All DI assembly goes in `src/api/wiring.py`, not in `app/main.py` lifespan.

## 2026-06-01 Pipeline Benchmark — 3 Bugs Found & Fixed

### Bug 1: ForeignKeyViolationError on pipeline state persistence
- **Problem**: `pipeline_run_states` has FK to `source_documents.source_document_id`, but pipeline endpoint creates new UUID without inserting parent row.
- **Root cause**: `state_persistence.py` INSERT into `pipeline_run_states` fails because `source_documents` row doesn't exist.
- **Fix**: Upsert `SourceDocument` before saving `PipelineRunState` in both `DirectStatePersistence` and `SessionBoundStatePersistence`.
- **File**: `backend/src/agents/state_persistence.py`

### Bug 2: State not persisted before semaphore acquisition
- **Problem**: When multiple pipeline runs are submitted concurrently, only runs that acquire the semaphore have their state persisted. Others return 404 on status poll.
- **Root cause**: `_persistence.save()` was inside `async with self._semaphore:` despite comment saying it should be before.
- **Fix**: Move `_persistence.save(initial_state)` and `_remember_state()` before the semaphore block.
- **File**: `backend/src/agents/runner.py`

### Bug 3: SOCKS5 proxy breaks MinerU TLS handshake
- **Problem**: `ALL_PROXY=socks5://127.0.0.1:7890` causes TLS handshake failure to `cdn-mineru.openxlab.org.cn`.
- **Root cause**: httpx/httpcore auto-detects SOCKS5 proxy from env. `no_proxy` does not work with SOCKS5.
- **Fix**: Clear proxy env vars (`ALL_PROXY`, `all_proxy`, `HTTPS_PROXY`, etc.) in `app/main.py` lifespan startup.
- **File**: `backend/app/main.py`

### Remaining Issue: LLM API 404
- `https://api.xiaomimimo.com/chat/completions` returns 404 for non-English PDFs needing translation.
- This is a configuration issue, not a code bug.

## 2026-06-02 并行 Agent Worktree 隔离失败

### 问题
使用 `isolation: "worktree"` 调度 5 个并行 agent 执行 6 个安全修复任务时，4/5 的 worktree 基于旧 commit（`a3c92ab3`，PR #14），而非当前 `dev` HEAD。导致 agent 在旧代码库（`apps/` 目录结构）上工作，无法找到目标文件（`backend/`）。

### 表现
- Agent 1, 3, 4, 5 的 worktree 分支上无新 commit
- 但它们的改动却出现在 `dev` 上 — 说明 agent 绕过 worktree 隔离直接修改了主分支
- Agent 2 是唯一正确使用 worktree 的（基于正确 commit，提交到 worktree 分支）

### 根因
1. **Worktree 创建基准错误**：`isolation: "worktree"` 创建 worktree 时使用了旧 commit 而非当前 `dev` HEAD。可能是 worktree 缓存或 git 状态不一致导致。
2. **TDD 流程未执行**：计划要求"先写失败测试 → 验证失败 → 实现 → 验证通过"，但所有 agent 一次性提交测试+实现，跳过了验证步骤。
3. **Worktree 隔离失效**：agent 发现 worktree 代码库不对后，自行决定直接在 `dev` 上操作，绕过了隔离机制。

### 验证
通过验证性回滚确认测试有效性：
- 临时移除 Task 2（文件大小限制）→ 测试返回 202（应为 413）→ 测试有效
- 临时移除 Task 3（路径遍历防护）→ 测试抛出 FileNotFoundError → 测试有效
- 恢复实现后所有 37 个 API 测试通过

### 预防措施
1. 使用 worktree 前先验证基准 commit 是否为当前 HEAD：`git log --oneline -1 <worktree-path>`
2. 对于修改同一文件的多个任务，不要使用并行 worktree — 改为顺序执行或合并到单个 agent
3. 在 agent prompt 中明确要求 TDD 验证步骤，并检查中间输出
4. 考虑使用 `git worktree add <path> <branch> --detach` 显式指定基准

## [2026-06-02] Phase 3 从未执行 — 根因是配置缺失而非模型问题

### 问题描述
Benchmark pipeline 中 Phase 3 (entity standardization) 在所有 10 份报告中均显示 `status=skipped, reason=not_relevant`。

### 排查过程
1. 初始诊断：Phase 2 relevance scan 返回 `relevant=False`，怀疑 FAST 模型不遵从 prompt
2. 尝试 prompt 强化（移动 DEFAULT 到顶部 + safety net）→ 无效
3. 升级到 STANDARD tier → 发现 "Missing credentials" 错误
4. **关键发现**：FAST tier 也有同样的 "Missing credentials" 错误！LLM 从未实际运行

### 根因分析
**配置缺失**：`EVIDENCE_EXTRACTION_*` 环境变量未配置。`evidence_extraction_api_key` 为空字符串，导致 ChatOpenAI 初始化时无法认证。

**静默失败链**：
1. LLM 调用抛出 "Missing credentials" 异常
2. `run_async()` 的 `return_exceptions=True` 捕获异常并记录 ERROR 日志
3. `maps` 列表为空（所有 chunk 失败）
4. `merge_evidence_maps([])` 静默返回 `DocumentEvidenceMap(relevant=False)`
5. 工作流将 `relevant=False` 解读为 NOT_RELEVANT → Phase 3 被跳过

### 解决方案
1. **config.py**：`evidence_extraction` 配置添加 fallback 到 `llm` 配置（与 `reasoning` 等模块一致）
2. **evidence_map.py**：当所有 chunk 失败时抛出 `RuntimeError` 而非静默返回 `relevant=False`
3. **prompts.py**：DEFAULT 指令移到 TASK 之前 + 不确定时默认 TRUE 的 safety net

### 预防措施
- 新增 LLM 配置域时，必须添加 fallback 到通用 LLM 配置
- `merge_evidence_maps([])` 不应静默返回默认值 — 应由调用方处理空列表情况
- 环境变量缺失应在启动时检测并警告，而非运行时静默失败

## [2026-06-02] Phase 3 修复代码审查 — 发现 3 个测试缺口 + 2 个持续管道故障

### 审查范围
对已完成的 Phase 3 benchmark coverage 修复（config fallback + RuntimeError + prompt 强化）
进行代码审查，验证修复有效性并识别剩余问题。

### 审查发现

#### 1. 修复代码正确，但测试覆盖不完整（3 个缺口）

| # | 缺口 | 文件 | 说明 |
|---|------|------|------|
| 1 | `evidence_extraction` 配置 fallback 无测试 | `test_config.py` | `config.py` lines 489-497 的 `or self.llm.*` fallback 无任何测试覆盖 |
| 2 | NOT_RELEVANT 分类 prompt 断言无测试 | `test_prompts.py` | prompt 已包含 "methodological"、"editorial" 等类别定义，但无对应测试 |
| 3 | all-chunks-fail RuntimeError 无测试 | `test_stages_async.py` | `test_stage_async_survives_chunk_failure` 只测试了部分失败（1/2 chunks），未覆盖全部失败场景 |

#### 2. 基准测试仍存在 2 个独立故障

最新报告（`report_20260602_172642.json`）显示 7 个测试用例：3 passed、4 failed。

**故障 A: PT (pt) + ZH 临时文件路径竞态**
- 错误：`Phase 2 transient error: No such file or directory: 'data/pipeline/.../phase_1/tmp.../metadata.json'`
- 路径中的 `tmp...` 来源于文件采集服务的 tempfile 名
- Phase 1 adapter 使用相对路径 `data/pipeline/{run_id}/phase_1/` 作为输出目录
- `parse_local_files_and_save` 以上传文件 stem 创建子目录 → 系统临时文件 stem 被用作持久化目录名
- 可能根因：CWD 敏感的相对路径，或 MinerU batch zip 中 `file_name` 字段在不同语言下的解析差异
- 需要运行时调试确认：服务器 CWD 是否与预期一致

**故障 B: RU (ru) 翻译原文未变**
- 错误：`Phase 2 unexpected error: translation_validation_failed: unchanged`
- 翻译 pipeline 对俄语输入输出了与输入相同的文本
- `_RETRYABLE_ERRORS` 不包含该错误 → 标记为不可重试的 `PermanentPhaseError`
- 需要检查翻译 pipeline 的俄语语言检测和翻译回退逻辑

#### 3. Phase 3 `no_candidates` 行为正常

3 个通过的用例均显示 `match_count=0, skip_reason=no_candidates`：
- en: 0 matches (COVID-19 case report, no HGVS variants)
- es: 0 matches
- ko: 0 matches

这些是简单的病例报告，可能确实不包含 HGVS 格式的变异表述。对于已知含 `c.92C>A` 的 Fabry 中文病例报告，
Phase 2 失败导致 Phase 3 未能执行（pipeline error），因此该结论需在 Fabry E2E 中验证。

### 建议的修复优先级
1. **低**：补充 3 个缺失的测试（config fallback + prompt categories + all-chunks-fail）
2. **中**：Fix PT/ZH temp file path — 将 Phase 1 output_dir 改为绝对路径或确保 CWD 一致
3. **低**：Fix RU translation — 对 `translation_validation_failed: unchanged` 添加 retryable 分类
4. **信息**：在 Fabry 病例上验证 Phase 3 匹配 — 确认 `no_candidates` 确实是预期行为

### 预防措施
- 新增 LLM 配置域后必须在 `test_config.py` 中写 fallback 测试
- prompt 的所有负例/正例分类约束必须有对应测试
- `return_exceptions=True` 的 gather 必须检查空结果 + 错误列表
- 管道输出路径应使用绝对路径或相对于项目根目录的稳定路径，避免 CWD 漂移


## 2026-06-02 后端安全修复三轮审查经验

### 问题
安全修复计划（6 任务）完成后，经过三轮代码审查发现 11 个问题（3 blocking, 5 important, 3 minor）。

### 第一轮发现
- Stream endpoint (GET /chat/sessions/{id}/stream) 缺少限流
- 请求体先读入内存再检查大小（内存 DoS）
- base64.b64decode 宽松模式（静默忽略非法输入）
- slowapi 使用内存存储（多 worker 限流状态分散）

### 第二轮发现
- BaseHTTPMiddleware 缓冲 SSE 响应（破坏流式传输）
- Windows 路径遍历未防护（PurePosixPath 仅处理 `/`）
- 分块传输编码绕过 Content-Length 检查
- rate_limit.py 导入时调用 get_config()

### 第三轮发现
- 分块传输超限后传空 body 给 app（应直接返回 413）
- 测试未真正验证分块编码路径
- slowapi 私有属性访问无版本约束注释

### 根因
1. 中间件选型不当：BaseHTTPMiddleware 缓冲所有响应
2. 安全边界考虑不周：仅检查 Content-Length，未考虑 chunked 编码
3. 平台差异遗漏：仅处理 Unix 路径分隔符
4. 测试覆盖不充分：测试名暗示验证的行为实际未被测试

### 解决方案
1. 改用原始 ASGI 中间件（不缓冲响应）
2. 包装 receive 累计实际字节数 + 包装 send 抑制重复响应
3. raw_fname.replace("\\", "/") 标准化
4. 用 raw ASGI scope + body-reading handler 测试 chunked 场景

### 预防措施
- 涉及 SSE/流式响应的中间件必须用原始 ASGI，不用 BaseHTTPMiddleware
- 安全检查必须覆盖所有传输编码（Content-Length + chunked）
- 路径处理必须同时考虑 Unix (/) 和 Windows (\\) 分隔符
- 测试必须验证其名称暗示的行为，不能仅靠间接验证
- 使用 slowapi 等库的私有属性时添加版本约束注释和 smoke test

## [2026-06-02] 在线获取模块重构：链接获取与下载分离

### 问题描述
原在线获取模块将链接获取和文件下载耦合在同一 API provider 调用链中，7 个 web provider 各自实现搜索+下载逻辑，难以维护和扩展。

### 排查过程
1. 分析现有代码结构：workflow.py 的 fallback chain、gateway.py 的 download_from_provider、search_service.py 的 LANG_PROVIDER_MATRIX
2. 识别各 provider 的 URL 提取模式差异（unpaywall inline、DOAJ/JStage explicit、crossref/europepmc embedded）
3. 确认 Rust PyO3 边界的类型转换机制（serde_json::json! → Python dict）

### 根因分析
- 架构上搜索和下载是同一函数的两个阶段，无法独立扩展
- web provider 每个需要独立维护搜索+下载逻辑
- 链接获取阶段的筛选逻辑与下载阶段耦合

### 解决方案
1. 三阶段流水线：链接获取（并行 API + Firecrawl）→ 下载（类型路由）→ LLM 门控
2. 适配器模式：WebSearchAdapter ABC + FirecrawlAdapter 实现，便于替换搜索后端
3. Rust download_file PyO3 绑定返回 dict（serde_json::json! 自动转换）
4. download_file_from_url 保留 HTML→PDF 重定向处理（queue-based approach）
5. 所有 asyncio.gather 使用 return_exceptions=True 防止单点失败

### 预防措施
- PyO3 返回类型：使用 serde_json::json! 返回 dict，不要返回 tuple（Python 侧难以类型安全地解构）
- Firecrawl SDK 响应可能是 Pydantic model 或 dict，使用 _to_dict() 统一处理
- 现有测试中引用已删除函数的情况需要在重构时一并更新
- web_providers.py 的废弃警告使用 per-function 而非 module-level，避免影响其他模块的 import

## 2026-06-04: catalog_extraction 静默吞掉异常 + Phase 3 未 commit

**问题描述**：benchmark pipeline 跑过后 PG 中 evidence=0，Phase 3 报告 "no candidates"。

**排查过程**：
1. 检查 PG `run_evidence_items` — 0 条记录
2. 检查 Phase 3 adapter — `standardized_count=0`，`skip_reason=no_candidates`
3. 检查 `DualResultAdapter` — 需要 `evidence_chains` 作为 candidates 来源
4. 检查 backend logs — `catalog_extraction chunk 1/1 failed: Request timed out.`
5. 检查 `catalog_extraction.py:113-124` — `asyncio.gather(return_exceptions=True)` + `continue` 静默跳过

**根因分析**：
- **问题 1 (基础设施)**：`api.xiaomimimo.com` LLM API 超时 300s
- **问题 2 (设计缺陷)**：`return_exceptions=True` + `continue` 把基础设施错误降级为数据问题，Phase 2 以 "成功" 状态结束但实际提取为空
- **问题 3 (代码 bug)**：Phase 3 adapter 使用 `async with session_factory() as session:` 但未调用 `session.commit()`，导致即使有证据也不会持久化

**解决方案**：
1. `catalog_extraction.py`：全量失败时抛 `CatalogExtractionError`，部分失败记录 warning
2. `phase_3_adapter.py`：添加 `await session.commit()`
3. LLM API 超时问题需在基础设施层解决（中转 API 稳定性）

**预防措施**：
- `return_exceptions=True` 不能和静默 `continue` 组合使用 — 必须有失败率判断和升级机制
- SQLAlchemy async session 默认不 auto-commit，业务代码需显式 commit

## 2026-06-04: ASGITransport 不触发 lifespan + from X import f 不受 patch 影响

**问题描述**：`test_lifespan_disposes_redis_on_shutdown` 失败，`dispose_engine` 未被调用。

**排查过程**：
1. `ASGITransport(app=app)` + `AsyncClient(transport=...)` 不触发 ASGI lifespan 事件
2. 直接调用 `app.router.lifespan_context(app)` 可正确触发
3. `from src.api.wiring import dispose_engine` 创建本地绑定，`patch("src.api.wiring.dispose_engine")` 不影响已绑定的引用

**根因分析**：
- httpx `ASGITransport` 不自动处理 lifespan（需显式调用或使用 `app` 参数）
- `from X import f` 拷贝引用，`patch("X.f")` 替换模块属性不影响已拷贝的引用

**解决方案**：
- 测试改用 `app.router.lifespan_context(app)` 直接触发 lifespan
- lifespan 中使用 `import src.api.wiring as _wiring` + `_wiring.dispose_engine()` 保持属性查找

**预防措施**：
- ASGI lifespan 测试不要依赖 httpx transport，直接用 lifespan context
- 需要被 mock 的函数不要用 `from X import f`，用模块属性访问

## 2026-06-04: 新增 wire_dependencies 步骤需同步更新 _patch_wire_deps mock 列表

**问题描述**：在 `wire_dependencies()` 中添加 `_redis_client = build_redis_client(cfg)` 后，`test_wiring_config.py` 的 2 个现有测试失败：`ValueError: "max_connections" must be a positive integer`。

**排查过程**：
1. `build_redis_client(cfg)` 中 `cfg` 是 `MagicMock`，`cfg.redis.max_connections` 返回 `MagicMock`（非 int）
2. `redis.asyncio.ConnectionPool` 要求 `max_connections` 为正整数

**根因分析**：
- `test_wiring_config.py` 的 `_patch_wire_deps` mock 列表未包含 `build_redis_client`
- 每次在 `wire_dependencies()` 中新增步骤，都需检查其 mock 列表是否完整

**解决方案**：
- 在 `_patch_wire_deps` 中添加 `"src.api.wiring.build_redis_client"` 到 patch 列表

**预防措施**：
- 修改 `wire_dependencies()` 后，运行 `test_wiring_config.py` 确认无回归
- 新增依赖注入步骤时，同步更新测试 mock 列表

---

## 2026-06-04 Pipeline Benchmark 真实测试复盘

### 问题描述
运行 pipeline benchmark 真实测试时发现 3 个问题：
1. Benchmark 提交 PDF 后立即轮询状态返回 HTTP 404
2. Phase 2 LLM formatting 无限挂死，pipeline 卡住
3. uvicorn `--reload` 反复重启后端，杀死正在运行的 pipeline

### 排查过程
1. **404 问题**：benchmark 的 `poll_status` 在 POST 返回后立即 GET 状态，但后端异步创建 run 记录，首次轮询时记录尚未入库
2. **挂死问题**：`TranslationConfigContext` 不含 `timeout` 字段，`formatter.py` 和 `translate/providers.py` 创建 `ChatOpenAI` 时未传 `timeout`，导致 LLM 调用无超时限制
3. **重启问题**：uvicorn `--reload` 默认监控整个 `backend/` 目录，pipeline 往 `data/pipeline/` 写文件触发重启死循环

### 根因分析
- **404**：后端 API 返回 run_id 和 status_url 是同步的，但 run 记录写入 DB 是异步的，存在时序差
- **超时缺失**：evidence extraction 和 reasoning LLM 正确设置了 timeout，但 translation/formatting 的 LLM 遗漏了
- **reload 范围过大**：`data/`、`__pycache__`、`*.pyc` 都在监控范围内

### 解决方案
1. `benchmark/pipeline/benchmark.py`：`poll_status` 对 404 响应做最多 15 次重试（2s 间隔）
2. `config_context.py`：`TranslationConfigContext` 添加 `timeout: int = 60`
3. `translate/providers.py`：`create_llm` / `create_json_llm` 添加 `timeout` 参数并传给 `ChatOpenAI`
4. `workflow.py`：formatter LLM 创建时传入 `timeout`
5. 后端启动加 `--reload-exclude "data/*" --reload-exclude "__pycache__" --reload-exclude "*.pyc"`

### 预防措施
- 新增 LLM 客户端创建点时，必须检查是否传入 `timeout`
- uvicorn `--reload` 必须排除运行时写入目录
- Benchmark 测试前先用 1 篇 PDF 做冒烟验证

## 2026-06-05: model_kwargs or None 导致 ChatOpenAI 初始化 TypeError

**问题描述**：`evidence_map` relevance_scan 阶段报 `TypeError: argument of type 'NoneType' is not iterable`，所有 chunk 全部失败。

**排查过程**：
1. 初始怀疑 `structured.ainvoke()` 返回 None → 添加 None guard → 无效
2. 怀疑 `with_structured_output(method="json_mode")` 解析失败 → 添加 TypeError fallback → 无效
3. 添加 full traceback logging → 发现错误在 `_client_for_tier()` 的 `ChatOpenAI()` 初始化
4. Traceback 指向 `langchain_core/utils/utils.py:235: if field_name in extra_kwargs`，`extra_kwargs` 为 None

**根因**：`providers.py` line 85: `model_kwargs=model_kwargs or None`。当 `model_kwargs={}` 时，`{} or None` 求值为 `None`（空 dict 是 falsy）。`ChatOpenAI(model_kwargs=None)` 导致 `_build_model_kwargs` 收到 `extra_kwargs=None`，`if field_name in None` 报 TypeError。

**修复**：改为 `**({"model_kwargs": model_kwargs} if model_kwargs else {})`，空 dict 时不传 `model_kwargs` 参数。

**同时修复**：evidence extraction timeout 从 60s 增加到 180s（REASONING_LLM 需要更长时间完成 catalog_extraction）。

**预防措施**：
- Python `or` 对空 dict/空 list/空字符串返回 falsy 值，不能用 `x or None` 做"有值才传"的逻辑
- LangChain `ChatOpenAI` 的 `model_kwargs` 不能传 `None`，只能传 `dict` 或不传
- 排查 LLM 调用错误时，先检查客户端初始化而非 LLM 响应

## 2026-06-05: Model Server 单元测试不能依赖真实 vllm 安装

**问题描述**：运行 `uv run pytest services/model-server/tests -v` 时，Model Server 测试 24 个中 16 个失败，失败集中在 `patch("app.domain.embedding.vllm.LLM")`、`patch("app.domain.vlm.MinerUClient")` 等 mock 路径解析。

**排查过程**：
1. 复现测试失败，确认不是业务断言失败，而是导入阶段失败。
2. 检查 `services/model-server/app/domain/*.py`，发现 `embedding.py`、`rerank.py`、`vlm.py` 在模块顶层直接导入 `vllm` / `mineru_vl_utils`。
3. 当前 `uv run pytest` 的基础环境没有安装 `backend[model-server]` 额外依赖中的 `vllm`，导致测试在 patch 前无法完成模块导入。

**根因分析**：
- Model Server 单元测试设计为 mock `vllm.LLM`，不需要真实 GPU 推理栈。
- 但被测模块在 import 阶段已经要求真实 `vllm` 存在，mock 还没机会生效。

**解决方案**：
- 在 `services/model-server/tests/conftest.py` 中安装 CPU-only 可选依赖占位模块。
- 占位模块只提供被测试 patch 的符号；若测试未 patch 就实际使用，会抛出清晰错误。

**预防措施**：
- GPU/大模型推理依赖的单元测试必须在测试启动阶段提供 mock/stub，或将真实依赖延迟到 `_load()` 等运行阶段导入。
- 验证 Model Server 测试时使用基础命令 `uv run pytest services/model-server/tests -v`，确保不隐式依赖本机 GPU 环境。

## 2026-06-06: 大文档 catalog_extraction 超时优化

**问题描述**：31 页 COVID-19 文档在 catalog_extraction 阶段超时失败（180s timeout），所有 chunk 全部失败。

**排查过程**：
1. 分析 chunking 逻辑：16K token budget → 31 页文档产生 1-3 个大 chunk
2. 分析模型配置：STRONG tier 使用 mimo-v2.5-pro + reasoning_effort=xhigh
3. 分析 timeout：evidence extraction 180s，reasoning model 300s，两者独立
4. 根因：16K token 大 chunk + xhigh reasoning effort + 180s timeout = 必然超时

**根因分析**：
- STRONG tier 使用 reasoning model（mimo-v2.5-pro）+ xhigh effort
- 16K token chunk 包含 120 个字段的 catalog 评估 + 大量文档文本
- Reasoning model 在 xhigh effort 下需要大量内部推理时间
- 180s timeout 不足以完成如此复杂的任务

**解决方案**：
1. **STRONG tier chunk size**: 16K → 8K tokens（更小但更快的 LLM 调用）
2. **Evidence extraction timeout**: 180s → 300s
3. **Max retries**: 3 → 2（避免无意义重试，每次 300s）
4. **Reasoning effort**: xhigh → high（减少内部推理时间）

**效果对比**：
| 指标 | 优化前 | 优化后 | 变化 |
|------|--------|--------|------|
| 平均耗时 | 1633s | 1003s | -38% |
| Evidence 总数 | 68 | 99 | +46% |
| Field coverage | 50 | 63 | +26% |
| Entity bindings | 375 | 742 | +98% |

**关键收益**：
- 31 页 COVID-19 文档从超时失败 → 1304s 通过，提取 60 evidence items
- 所有通过的 PDF 提取了更多 evidence（46% 增加）
- Entity bindings 翻倍（98% 增加）

**预防措施**：
- Reasoning model 的 chunk size 应比非-reasoning model 小（8K vs 16K）
- 大文档处理需要平衡 chunk size 和 timeout：小 chunk = 更多调用但每个更快
- Reasoning effort 应根据任务复杂度选择，xhigh 对结构化提取过度
- 测试大文档（>20 页）应作为 benchmark 的标准用例

## 2026-06-06: 配置清理时聚焦 Ruff 暴露陈旧导入

**问题描述**：运行聚焦 Ruff 检查时，`backend/tests/core/test_config.py` 报 `F401 pathlib.Path imported but unused`。

**排查过程**：
1. 读取 Ruff 输出，确认唯一失败点是未使用导入。
2. 检查本次改动，确认该文件只更新了配置来源注释，但既然文件已被触碰，应保持 lint clean。

**根因分析**：`Path` 是此前遗留的未使用导入；本次聚焦检查覆盖了该文件后暴露出来。

**解决方案**：删除 `from pathlib import Path`。

**预防措施**：修改测试文件时，同步运行聚焦 Ruff；对已触碰文件里的陈旧 import 及时清理。

## 2026-06-07: Layer 3 ClinGen-based Pipeline Evaluation

**问题描述**：需要建立自动化评估框架衡量 pipeline 证据提取准确性。

**实现方案**：
1. 从 ClinGen Gene-Disease Validity CSV 选取 30 条代表性评审（Definitive/Strong/Moderate/Limited/Refuted/Disputed）
2. 通过 EuropePMC API 查询 PMC 全文 ID
3. 通过 NCBI efetch API 获取 JATS XML 全文
4. 转换为 PDF 提交 pipeline
5. 对比提取结果与 ClinGen ground truth

**技术难点**：
- PMC PDF 直接下载受限（HTTP 404/405），改用 NCBI efetch XML API
- EuropePMC HTML 是 SPA（需 JavaScript），无法直接提取文本
- fpdf2 不支持 Unicode，需 latin-1 编码处理
- LLM API 响应慢导致评估耗时数小时

**基线结果（3 条 Definitive entries）**：
- Gene symbol 提取准确率：100%
- Disease name 匹配率：低（ClinGen 标准名 vs 文献原始描述）
- Overall P=40% R=67% F1=50%

**产出文件**：
- `benchmark/layer3/select_entries.py` — ClinGen 选取脚本
- `benchmark/layer3/fetch_literature.py` — EuropePMC 查询
- `benchmark/layer3/download_pdfs.py` — NCBI efetch 全文获取
- `benchmark/layer3/evaluate.py` — 评估脚本（P/R/F1）
- `benchmark/layer3/ground_truth/` — 30 条 ground truth 数据

**预防措施**：
- PMC 全文获取应优先使用 NCBI efetch API（返回 XML），而非直接下载 PDF
- fpdf2 需要 latin-1 编码，Unicode 字符需预处理
- 评估脚本应支持断点续评（避免超时后重新开始）

## 2026-06-07: LLM API Key Pool — 适配器模式实现

**问题描述**：单 API key 在高并发场景下容易触发限流（429），需要支持多 key 轮询。

**实现方案**：适配器模式 + round-robin 轮询 + 认证错误自动切换

**架构设计**：
```
config/vault/development.yaml
  fast_llm:
    api_keys: [key1, key2, key3]
       ↓
config.py: LLMConfig.all_api_keys → 去重合并
       ↓
config_context.py: TranslationConfigContext.api_keys / EvidenceExtractionConfigContext.api_keys
       ↓
llm_adapter.py: create_llm_client() → LLMPoolAdapter
       ↓
LLMPoolAdapter: round-robin 轮询 + 401/403 自动 failover
```

**改动文件**：
- `src/utils/llm_adapter.py` — 新建：LLMPoolAdapter + create_llm_client 工厂
- `src/core/config.py` — LLMConfig/ReasoningConfig 添加 api_keys 字段 + all_api_keys 属性
- `src/core/config_loader.py` — YAML list → 逗号分隔 env var
- `config_context.py` — TranslationConfigContext/EvidenceExtractionConfigContext 添加 api_keys
- `extract_evidence/providers.py` — _client_for_tier 改用 create_llm_client
- `cross_lingual/translate/providers.py` — create_llm/create_json_llm 改用 adapter
- `workflow.py` — formatter LLM 改用 adapter
- `cross_lingual/translate/translator.py` — 传递 api_keys

**关键设计**：
1. `LLMPoolAdapter` 暴露与 `ChatOpenAI` 相同的接口（.invoke/.ainvoke/.with_structured_output）
2. `_StructuredOutputWrapper` 包装 with_structured_output 以支持 key 轮询
3. `_is_auth_error()` 检测 401/403 错误触发 failover
4. 向后兼容：单 key 配置仍然工作

**预防措施**：
- YAML 的 list 字段在 flatten 时需转为逗号分隔字符串
- 适配器必须暴露与原客户端完全相同的接口

## 2026-06-07: Frontend Chat SSE `/chat/sessions/stream` 405

**问题描述**：聊天页面请求 `POST /api/v1/chat/sessions/stream`，后端返回 405。后端实际路由是 `GET /api/v1/chat/sessions/{session_id}/stream`。

**排查过程**：
- 对照浏览器错误、前端 `acmgChatProvider.ts`、`ChatView.tsx` 与后端 `chat.py` 路由。
- 发现 `FullChatView` 在无 active session 时用空字符串构造 provider，导致 URL 折叠为 `/chat/sessions/stream`。
- 继续检查 `@ant-design/x-sdk` 的 `XRequest` 实现，确认其默认强制使用 `POST`，即使配置的是 stream URL。
- 同时发现后端返回字段为 `chat_session_id`，前端类型和组件使用 `session_id`，会让新建会话后 active key 为空。

**根因分析**：
- 前端会话响应契约未适配后端字段名，导致 session id 丢失。
- 前端在没有 session id 时仍创建 SSE provider。
- Ant Design XRequest 默认 POST，与后端 SSE GET 契约不一致。

**解决方案**：
- 在 chat service 层把后端 `chat_session_id` 归一化为前端 `session_id`。
- `ChatView` 仅在存在 `activeConversationKey` 时创建 provider。
- `AcmgChatProvider` 使用自定义 `fetch` 发起 GET，并把最新用户消息写入 `user_message` query 参数。

**预防措施**：
- 前后端 API 字段名不一致时必须在 service 边界显式归一化，避免组件直接依赖后端 raw schema。
- 第三方请求 SDK 的默认 method 必须验证，尤其是 SSE/streaming 场景。
- 对需要 path 参数的 provider，不允许使用空字符串作为临时 id。

## 2026-06-08: Literature Profile Read Model Review Catches

**问题描述：** 新增 literature_profiles API 端点时，出现两个遗漏。

**排查过程：**
1. `LiteratureProfileDetailResponse` 定义了 `review_notes` 字段，但路由处理器构造响应时漏传了该字段，导致数据静默丢失（字段有 None 默认值）。
2. `EvidenceGroupSummary.summary` 使用裸 `dict` 类型，违反项目 rule 22 类型安全规范。

**根因分析：**
1. Pydantic 模型字段有默认值时，漏传不会报错，容易被忽略。
2. 快速实现时未逐条对照 rule 22 检查所有新添加的类型标注。

**解决方案：**
1. 补传 `review_notes=profile.get("review_notes")`。
2. 新增 `EvidenceGroupSummaryDict(TypedDict)` 替代裸 `dict`，`authors: list` 改为 `list[str]`。

**预防措施：**
- 路由处理器构造 Pydantic response 时，必须逐一对照模型字段列表，确保每个字段都有显式赋值。
- 新增 Pydantic 模型后，立即用 `grep -n "dict\|list" contracts.py` 检查是否有裸类型违反 rule 22。

## 2026-06-08: SQLite/PostgreSQL JSONB DDL 兼容问题

**问题描述：** SQLite 执行 PostgreSQL 特有的 `DEFAULT '[]'::jsonb` DDL 时报 `sqlite3.OperationalError: unrecognized token ":"`。

**根因分析：** PostgreSQL 的 `::type` 类型转换语法在 SQLite 中无法识别。ORM 模型和 Table 定义中的 `server_default=text("'[]'::jsonb")` 在 SQLite `create_all()` 时会产生无效 DDL。

**解决方案：** 将 `server_default=text("'[]'::jsonb")` 改为 `server_default=text("'[]'")`。PostgreSQL 在列类型为 JSONB 时会隐式完成类型转换，无需显式 `::jsonb` 转换。

**影响范围：**
- `backend/src/dao/postgresql/models.py` — ORM 模型（已由子代理修复）
- `backend/src/dao/postgresql/search_index_repo.py` — frontend_search_index Table 定义（4 处修复）

**预防措施：**
- 新增 JSONB 列的 `server_default` 时，只写 `text("'[]'")` 或 `text("'{}'")`，禁止加 `::jsonb` 后缀。
- `grep -rn "::jsonb" src/dao/` 定期检查 ORM 层是否有遗漏（migration 文件不在此限，因 migration 仅在 PostgreSQL 上执行）。

## 2026-06-08: Evidence Detail React Hooks Lint

**问题描述：** 重构 evidence detail 双文对照页后，`npm run lint` 报 `react-hooks/set-state-in-effect`，指出组件在 `useEffect` 中同步调用 `setSelectedEvidenceId()`。

**排查过程：**
- 对照 ESLint 报错位置，确认 effect 只用于把 `detail + initialEvidenceId` 推导出的初始 evidence id 写入 state。
- 检查组件数据流，发现该值不是外部系统同步结果，而是可由 props 和 query 数据直接派生。

**根因分析：** 将派生状态落入 React state，导致初次渲染后立刻同步 setState，触发 React hooks 规则，并增加不必要的二次渲染。

**解决方案：** 删除同步 effect，改为 `useMemo` 从 `detail`、`initialEvidenceId` 和用户手动选择的 `selectedOverrideId` 派生最终 `selectedEvidenceId`。只有用户在对照页切换证据项时才写入 state。

**预防措施：**
- URL 参数和查询结果可直接推导出的 UI 状态不要放入 effect 同步。
- 需要“初始值 + 用户覆盖”的场景，优先使用派生值加 override state。

## 2026-06-08: Frontend Test Build Artifacts Entering ESLint

**问题描述：** 新增 Node 原生测试编译流程后，`npm test` 会输出 `.test-build/`。随后执行 `npm run lint` 时，ESLint 扫描该目录中的 CommonJS 编译产物并报 `@typescript-eslint/no-require-imports`。

**排查过程：**
- 先运行 `npm test`，确认测试会生成 `.test-build/`。
- 再运行 `npm run lint`，错误文件全部位于 `.test-build/`，且不是源 TS/TSX 文件。
- 检查 `frontend/.gitignore`，确认 `.test-build/` 已被 git 忽略，但 ESLint 配置没有忽略该目录。

**根因分析：** `.gitignore` 只影响版本控制，不会自动约束 ESLint 扫描范围。测试编译产物使用 CommonJS 输出，触发源代码 lint 规则属于工具范围配置问题。

**解决方案：** 在 `frontend/eslint.config.mjs` 中添加 `ignores: [".test-build/**"]`，让 lint 只检查源文件和配置文件。

**预防措施：**
- 新增测试编译输出目录时，同时更新 `.gitignore` 和 ESLint ignore。
- CI/本地验证顺序包含 `npm test && npm run lint`，确保测试产物不会污染后续 lint。

## 2026-06-09: FeedbackService 新增写后刷新时旧 mock 测试需要隔离新 side effect

**问题描述：** 给 `FeedbackService.patch_evidence()` 增加 `_refresh_search_index()` 后，旧的 profile refresh 单元测试失败，真实 `SearchIndexRepository.refresh()` 在 `MagicMock` session 上执行到 `await commit()` 并报错。

**排查过程：**
- 先运行新增 RED 测试，确认失败点是缺少 `refresh_search_index` 调用和 `_refresh_search_index` 方法。
- 实现后重跑 focused tests，发现新增测试通过，但两个旧测试失败。
- 阅读堆栈，确认失败来自旧测试只 mock `_refresh_literature_profile()`，没有 mock 新增的 `_refresh_search_index()`。

**根因分析：** 新增 search-index refresh 是 patch 后的真实 side effect。旧测试使用 `MagicMock` session 并没有为真实 repository 的 async `commit()` 提供 awaitable mock，因此测试边界不再完整。

**解决方案：** 在旧测试中显式 patch `_refresh_search_index()`，保留原有 profile refresh 和 audit ordering 断言；新增独立测试验证 `_refresh_search_index()` 会委派给 `SearchIndexRepository.refresh()`。

**预防措施：** 服务方法新增写后 side effect 时，同步检查所有 patch 级单元测试是否需要隔离该 side effect，并为新增 side effect 添加单独委派测试。

## 2026-06-09: Bilingual comparison review follow-up

**问题描述：** 原文/译文对照高亮在缺失 offset、文档全局 offset、短基因符号和前端 fallback 场景下不稳定；online acquisition 的 Firecrawl/web 路径错误不可观测；evidence provider 缺 API key 时错误信息滞后且不清晰。

**排查过程：**
1. 对照 review 列表逐项检查当前 `dev` 实现，确认部分反馈来自另一工作树路径，但核心问题在当前模块仍存在。
2. 先跑相关测试，发现基线已有 SearchIndex 契约测试和 provider mock 测试失配，以及前端 Node 测试 TypeScript 空值收窄失败。
3. 为缺失 offset、两字符基因符号、prefer=web 失败、source_trace、下载异常日志、provider 缺 key、前端 value fallback 补复现测试。

**根因分析：**
1. `_build_highlight()` 把缺失 offset 当作合法 `0/text_len`，导致无 offset 时整段或错误区间被高亮。
2. value fallback 用固定 `len(value) >= 3` 门槛，避免了单字符误报，但也误杀了 `RB` 这类两字符大写基因符号。
3. workflow phase 1 没有按 `prefer` 分支建立清晰的错误处理和 trace 记录，`gather(return_exceptions=True)` 后也丢弃了非下载结果异常。
4. provider 直接把空 key 池交给底层 LLM adapter，导致错误延迟到客户端初始化或首次调用。

**解决方案：**
1. offset 解析改为保留 `None`，缺失/越界时优先用安全 value anchor；两字符 fallback 只允许独立的大写 token，单字符仍禁用。
2. workflow 尊重 `prefer=web/api/auto`，失败时写入 warnings，并在 `raw.source_trace` 暴露 provider trace。
3. `_download_candidates()` 对 unexpected exception 写 warning，避免静默丢弃。
4. `LangChainEvidenceProvider` 在创建客户端前合并单 key 和 key pool，并对空 key 池快速抛出明确配置错误。
5. 前端 full-text reader 增加同样的安全 value fallback，测试用显式类型收窄避免 `node:assert` 无法帮助 TypeScript 缩窄类型。

**预防措施：**
- 高亮逻辑必须区分“offset 缺失”“offset 可解析但越界”和“offset 合法需 clamp”三种状态。
- `return_exceptions=True` 的结果必须逐项记录异常，不允许只用 `isinstance(success_type)` 过滤。
- LLM provider 初始化前必须验证配置契约，避免把空凭证传给底层客户端。

## 2026-06-09 Hide empty English translation track — data-availability follow-up

- Problem description: After merging the initial fix, `showTranslatedDocument = paragraphs.length > 0` collapsed the translated reader and the two-column grid whenever category/tone filters hid every translated span, even when the API had delivered translated content.
- Investigation process: Re-read `buildEvidenceDocument` to confirm the no-fullText branch returns 0 paragraphs whenever filter state empties the trace list, and confirmed the component's `length > 0` condition cannot tell data-absence from filter-state.
- Root cause: UI was using a render-time consequence of the filter as a proxy for data availability.
- Solution: Compute availability from `detail.translated_document_text?.trim()` and `traces.translated?.text`; let `EvidenceDocumentReader`'s existing empty-state handle the filter-to-zero case.
- Prevention: Distinguish "API gave us nothing" from "current filter selection renders nothing" at the predicate; never use a downstream rendered count to make a structural visibility decision.
- Follow-up: Collapsed two near-duplicate null/undefined tests into one with a comment explaining the shared code path; fixed an orphaned `docs/README.md` table row that was placed below a blank line.

## 2026-06-09 Empty English translation track displayed for English originals

- Problem description: The bilingual evidence detail page showed an `English translation` reader with `0 aligned paragraphs` when the original document was already English and no translated text existed.
- Investigation process: Searched the frontend and backend for bilingual evidence rendering, confirmed `EvidenceDetailView.tsx` always renders both original and translated readers, and confirmed `buildEvidenceDocument` can legitimately return an empty translated document.
- Root cause: The compare view treated the translated track as present based on the view mode alone, instead of checking whether the translated document had any non-empty paragraphs.
- Solution: Plan an inline `translatedDocument.paragraphs.length > 0` check and conditionally render the translated reader only when content exists.
- Prevention: Preserve existing imports in implementation plans and prefer existing empty-state signals before adding helper abstractions.
- Follow-up: Plan review found the helper and import snippet were unnecessary and could mislead implementation by dropping existing category imports. Revised the plan to use the existing `translatedDocument.paragraphs.length > 0` state directly and document both `null` and `undefined` missing-translation inputs.

## 2026-06-10: model-server migration plan Batch 1 checkpoint

**Problem:** Batch 1 execution started from a `dev` state that already contained the model-server migration commits. The first verification attempt for `libs/config-loader` failed with `Failed to spawn: pytest`.

**Investigation:** `libs/config-loader/pyproject.toml` already declares `pytest` under the `dev` optional dependency group. The failing command used `uv run --project libs/config-loader pytest ...`, which does not install optional dev dependencies for that project.

**Root cause:** The verification command omitted `--extra dev`, so the isolated config-loader environment did not contain pytest.

**Solution:** Re-ran the shared loader verification with `uv run --project libs/config-loader --extra dev pytest libs/config-loader/tests -v`.

**Verification:**
- Shared loader tests: 4/4 passed.
- Backend config-loader shim verification initially blocked because full backend environment synchronization timed out; later completed with scoped test dependencies: 2/2 passed and ruff clean for `src/core/config_loader.py`.

**Prevention:** Use the package's declared optional dependency group when verifying standalone Python packages with test-only dependencies, and avoid recording full migration/test completion until every verification step has completed successfully.
- For `sys.path.insert(...)` workarounds, the smell is the right trigger: any time a module reaches up to a parent's tree to import a sibling, it's a sign the sibling should be a proper installable package.

## 2026-06-11: model-server migration Batch 2 verification

**Problem:** The migration branch already contained Tasks 4–6, but plan verification commands that sync full backend/model-server environments were either previously timed out or would install heavy service dependencies unnecessarily.

**Investigation:** The touched files for Tasks 4–6 were already in their intended state: `backend/pyproject.toml` depends on editable `acmg-config-loader`, `backend/src/core/config_loader.py` is a re-export shim, `services/model-server/app/config.py` imports `acmg_config_loader` directly, and `services/model-server/pyproject.toml` defines the standalone service skeleton.

**Root cause:** Full-project `uv run` verification couples small config-loader checks to large backend/model-server dependency graphs. Backend tests also import global `tests/conftest.py`, which requires database-related packages even for the targeted config-loader tests.

**Solution:** Verified the touched contracts with scoped `uv run --no-project --with ...` commands that install only the dependencies required by the targeted tests and ruff checks.

**Verification:**
- `libs/config-loader`: 4/4 tests passed and ruff clean.
- `backend`: `tests/core/test_config_loader.py` passed 2/2 with scoped dependencies; `ruff check src/core/config_loader.py` clean.
- `services/model-server`: `tests/test_config_loader_path.py` passed 1/1 with scoped dependencies; `ruff check app/config.py tests/test_config_loader_path.py` clean.

**Prevention:** For migration checkpoints, prefer exact touched-file verification when full dependency synchronization is unrelated to the change and known to be slow; record the command scope explicitly so results are not mistaken for full-suite verification.

## 2026-06-11: model-server migration Batch 3 verification

**Problem:** Tasks 7–9 were already applied in the migration branch, but full model-server verification initially failed under scoped dependencies.

**Investigation:** The first full-suite scoped command omitted `fastapi`, then the retry omitted `numpy`. The failures were import-time errors (`ModuleNotFoundError: No module named 'fastapi'`, then missing `numpy` causing patch target resolution failures for `app.domain.embedding` and `app.domain.rerank`). The codebase's `tests/conftest.py` already stubs GPU-only `vllm` and `mineru_vl_utils`, so no real GPU dependency was needed.

**Root cause:** The scoped verification environment did not include all non-GPU runtime dependencies imported by the model-server modules before tests patch GPU interfaces.

**Solution:** Re-ran the model-server suite with scoped dependencies including `fastapi`, `uvicorn`, `httpx`, `pydantic`, `pydantic-settings`, `pyyaml`, `pillow`, `loguru`, `numpy`, pytest tools, and editable `acmg-config-loader`.

**Verification:**
- `services/model-server/tests/test_model_server_config.py` + `tests/test_config_loader_path.py`: 6/6 passed.
- Full `services/model-server/tests/`: 26/26 passed with CPU-only optional dependency stubs.
- `ruff check app/ tests/`: clean.
- `scripts/start_model_server.sh` resolves to `services/model-server/main.py`.
- Deploy Ansible role YAML parses and systemd template renders `WorkingDirectory=/srv/cross-evidence/services/model-server` plus the expected `uv run python main.py --port 8001` command.

**Prevention:** When using scoped `uv run --no-project --with ...` verification, include every import-time runtime dependency, not only test tools and the specific dependency being exercised.

## 2026-06-11: model-server migration Batch 4 verification

**Problem:** Tasks 10–12 were already applied, but one verification attempt used `ruff check pyproject.toml.jinja`, which failed with TOML/Python syntax errors because the file contains raw Jinja control syntax.

**Investigation:** The actual task requirement is to ensure the backend template no longer includes a `model-server` extra and still renders/parses correctly. Linting the raw `.jinja` file does not test that contract.

**Root cause:** The verification targeted the template source with the wrong tool instead of rendering the template first.

**Solution:** Rendered `backend/pyproject.toml.jinja` with representative Copier context, parsed the rendered TOML with `tomllib`, and asserted `project.optional-dependencies` has no `model-server` key.

**Verification:**
- `services/model-server/README.md` has no stale `backend/services/model-server` path.
- `backend/pyproject.toml` and `backend/pyproject.toml.jinja` have no `model-server` extra or `vllm` reference.
- `backend/uv.lock` has no `name = "vllm"` or `name = "xgrammar"` entries.
- `uv lock` in `backend/` resolves successfully.
- Backend config-loader targeted tests pass 2/2 with scoped dependencies.
- `services/model-server/main.py.jinja` renders with representative Copier context.
- `copier.yaml` excludes `services/model-server/main.py`, and both `services/model-server/main.py` and `.jinja` exist.

**Prevention:** For template files, verify the rendered artifact and parse it with the target format parser; do not lint the raw Jinja source as if it were TOML/Python.

## 2026-06-11: model-server migration Batch 5 final verification

**Problem:** Final documentation grep found historical `backend/services/model-server` references under `docs/archive/`, while active docs/root docs were clean.

**Investigation:** The migration plan's active-doc verification targets `README.md`, `backend/README.md`, `docs/active/`, `docs/README.md`, and `AGENTS.md`. Archive documents preserve historical plans/reviews and still mention old paths by design.

**Root cause:** A broad `docs/` grep includes archived historical records that are not current project guidance.

**Solution:** Verified active documentation separately from archived history, and used source-only grep for code/config/scripts.

**Verification:**
- Root/active docs: no stale `backend/services/model-server` references in `README.md`, `backend/README.md`, `docs/README.md`, `docs/active/`, or `AGENTS.md`.
- Source/config/script grep: `rg -n "backend/services/model-server" --type py --type toml --type yaml --type sh` returned no output.
- `libs/config-loader`: 4/4 tests passed and ruff clean.
- `services/model-server`: 26/26 tests passed and ruff clean.
- `backend`: `tests/core/test_config_loader.py` passed 2/2 and `src/core/config_loader.py` ruff clean.
- `backend/uv.lock`: no `vllm` or `xgrammar` package entries after `uv lock` resolution.
- Acceptance paths: `services/model-server/uv.lock` exists, `libs/config-loader/` exists, `backend/services/` no longer exists.
- `scripts/start_model_server.sh` resolves to `services/model-server/main.py`; Ansible systemd template renders `WorkingDirectory=/srv/cross-evidence/services/model-server` and the expected `uv run python main.py --port 8001` command.

**Prevention:** Separate current documentation checks from archived historical records; archive docs can preserve old paths, while active docs and source/config/scripts must reflect current layout.


## 2026-06-12 — Off-by-one in `_load_full_document_text` collapses evidence detail to highlight snippets

**Problem:** Frontend `BilingualComparison` on `/evidence/detail?view=compare` only rendered the small highlight snippets instead of the full document body with overlays. User reported the reader should "show the full text, not just the evidence items."

**Investigation:** The compare-mode reader renders `detail.original_document_text` / `detail.translated_document_text` (full text + overlays) when populated, and otherwise falls back to per-trace highlight snippets — exactly the symptom. Tracing the backend: `SearchService.get_group_detail` calls `_load_full_document_text(source_document_id, track=...)`, which had a hard-coded `Path(__file__).resolve().parents[4] / "data" / "pipeline"`. From `backend/src/core/visualize_evidence_with_expert_in_loop/search_service.py` that resolves to `<repo>/data/pipeline` — but the phase-2 outputs are written to `backend/data/pipeline` (4 levels up, inside the backend package, as documented in the project README). The directory never existed, so the function always returned `None` and the frontend silently fell back to highlight snippets only.

**Root cause:** An off-by-one in a `Path(__file__).resolve().parents[N]` index. Such indices are fragile because they depend on the file's depth in the package tree and break silently the moment the file moves or the package is renamed. The project already exposes stable `BACKEND_ROOT` and `REPO_ROOT` constants in `src.core.config` for exactly this kind of anchor.

**Solution:**
- Replaced the `parents[4]` index with `BACKEND_ROOT / "data" / "pipeline"` (primary) and added `REPO_ROOT / "data" / "pipeline"` as a fallback so the loader still works if the data directory is relocated or the deployment layout changes.
- Narrowed the catch-all `except Exception` to `(OSError, json.JSONDecodeError)` so unexpected errors surface instead of being silently swallowed.
- Added 3 unit tests covering: backend-root read, missing-data returns `None`, repo-root fallback.

**Verification:**
- `uv run ruff check src/core/visualize_evidence_with_expert_in_loop/search_service.py` — all checks passed.
- `uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_search_service.py` — 16/16 passed (13 pre-existing + 3 new).
- 22 unrelated pre-existing test failures in the full suite were verified to fail on the unchanged baseline (sqlite vs postgres `TRUNCATE` syntax) and are not caused by this change.
- After backend restart, `GET /api/v1/evidence/groups/detail?group_id=...` returns a non-null `original_document_text` and `translated_document_text`, so the frontend's `buildEvidenceDocument()` will render the full text with category highlights.

**Prevention:**
- Never use `Path(__file__).resolve().parents[N]` for project-relative paths. Always anchor to a named constant exposed from `src.core.config` (`BACKEND_ROOT`, `REPO_ROOT`) or a config-driven setting. The N-index is invisible to a reader and silently wrong if the file is moved.
- When a function's "return None" path hides a missing resource, add an integration smoke test (e.g. start backend, hit the endpoint, assert the field is non-null) — unit tests on the data layer alone won't catch a path-resolution bug of this shape.
- The frontend's silent fallback (render snippets when full text is missing) was the user-visible symptom. Frontend fallbacks should be explicit (an empty-state banner), not invisible.

## 2026-06-12 — Ant Design X chat messages can repeat `msg_0` after hook remounts

**Problem:** The chat page emitted React's duplicate child key warning for `msg_0` at `ChatPage -> ChatView`.

**Investigation:** `ChatView` passed `useXChat()` message IDs directly to `Bubble.List` item keys. The installed `@ant-design/x-sdk` creates local message IDs with a hook-local counter (`msg_0`, `msg_1`, ...), while its message store is global by `conversationKey`. When the hook remounts or another chat view binds the same conversation, the counter can restart while the global store still contains prior local messages.

**Root cause:** SDK-generated message IDs are unique only within one hook instance, not necessarily within the persisted conversation store used across remounts. Rendering those IDs directly as React keys makes duplicate `msg_0` entries possible.

**Solution:** Added `toUniqueChatMessageKeys()` to disambiguate repeated SDK IDs at render time without mutating SDK message IDs. `FullChatView` and `SingleSessionChat` now pass those unique keys to `Bubble.List`. The history mapper also uses a type guard so system-role backend messages are filtered before building `ChatBubbleMessage` values.

**Verification:**
- Red-green frontend regression test: duplicate IDs `msg_0`, `msg_0`, `msg_1`, `msg_0` map to unique keys `msg_0`, `msg_0__2`, `msg_1`, `msg_0__3`.
- `source ~/.nvm/nvm.sh && nvm use && npm test`: 26/26 frontend tests passed.
- `npm run type-check` is still blocked by unrelated pre-existing pipeline status type mismatches.
- `npm run lint` is still blocked by unrelated pre-existing `react-hooks/set-state-in-effect` errors in `PipelineStartForm.tsx` and `useChatSessions.ts`.

**Prevention:** Do not mutate Ant Design X SDK message IDs during streaming because `useXChat` uses them internally for updates. If the SDK ID source is not globally unique, derive render-only keys at the list boundary and cover duplicate-ID cases with utility tests.

<<<<<<< HEAD
## 2026-06-12 — Chat action requests were routed to silent note intent

**Problem:** The chat page displayed empty assistant bubbles after inputs such as `hi` and `I want to do literature evidence extraction`. Natural-language requests to start extraction did not open the embedded pipeline card, and database lookup requests were not routed to the evidence search experience.

**Investigation:** The frontend only handled action routing from prompt button clicks. Free-form Sender input always persisted the user message and opened the backend SSE stream. Backend `ChatService._detect_intent()` classified non-question, non-correction text as `note`; `stream_reply()` returned without yielding tokens for notes. Ant Design X then had no assistant content to render, producing the visible empty robot bubble.

**Root cause:** Action intent was split across UI prompts and backend chat intent detection. The free-form message path lacked deterministic routing for product actions, while backend note intent was too narrow for standalone conversational greetings and action requests.

**Solution:** Added a small frontend intent classifier for chat actions. Extraction and upload requests now open the existing `PipelineStartForm`; database/evidence lookup requests route to `/evidence`; unrelated text continues through chat. Backend question patterns now include greetings and standalone extraction/search/upload requests so direct chat streams do not silently return for these inputs.

**Verification:**
- Frontend red-green regression: `detectChatActionIntent("我想做文献的证据提取")` -> `start-pipeline`, upload text -> `upload-pdf`, database lookup -> `search-evidence`, `hi` -> `chat`.
- Backend red-green regression: `_detect_intent("我想做文献的证据提取")` and `_detect_intent("hi")` now return `question`.
- `source ~/.nvm/nvm.sh && nvm use && npm test`: 30/30 frontend tests passed.
- `source ~/.nvm/nvm.sh && nvm use && npm run lint`: passed.
- `source ~/.nvm/nvm.sh && nvm use && npm run type-check`: passed.
- `uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_chat_ai.py tests/core/visualize_evidence_with_expert_in_loop/test_chat_sse.py -q`: 14/14 passed.
- `uv run ruff check src/core/visualize_evidence_with_expert_in_loop/chat_service.py tests/core/visualize_evidence_with_expert_in_loop/test_chat_ai.py`: passed.

**Prevention:** Keep product action routing deterministic at the UI boundary before starting SSE. Backend chat intent should still treat standalone greetings and action requests as reply-worthy, while evidence-bound notes can remain silent only when the UI intentionally uses that mode.

## 2026-06-12: Bilingual comparison rebase — pre-existing branch with stale plan

**Problem:** The user invoked `/executing-plans bilingual-comparison-ux │ feat/bilingual-comparison-ux`, but the `feat/bilingual-comparison-ux` branch already had 4 plan commits from 2026-06-08 sitting on top of an older dev base. The 4 dev commits between the merge-base and current dev (chat duplicate keys, pipeline run history, nginx, cache-only-terminal) plus extensive Phase 2/3/4 work had not been merged into the branch. The plan's `BilingualComparison` component had a `trace: EvidenceTrackTrace | null` API, but dev had since refactored `EvidenceDetailView` to call it with a richer `detail/groupId/selectedEvidenceId/setSelectedEvidenceId` API.

**Investigation:** Discovered the existing worktree at `~/.config/superpowers/worktrees/01_ACMG_Lingua/bilingual-comparison-ux` (with 16 unrelated WIP files from Phase 2/3 work). The plan's 4 commits were valid (Task 1–4) but they sat on a 4-day-stale dev base. Confirmed 13-file intersection between the two branches: `contracts.py`, `search_service.py`, two test files, plan doc, `docs/README.md`, `package.json`, two evidence components, `index.ts`, `evidence-search/README.md`, `types/evidenceSearch.ts`, `lesson.md`, `progress.txt`.

**Root cause:** The plan was correctly executed on 2026-06-08, but the branch was never merged back to dev. While the branch waited, dev drifted forward 4 commits, including the `EvidenceDetailView` rewrite that changed how `BilingualComparison` was called.

**Solution:** Opened `.worktrees/merge-bilingual-comparison-ux` on a fresh `merge/bilingual-comparison-ux-onto-dev` branch from current dev HEAD. Cherry-picked the 4 plan commits sequentially, resolving 13 conflict regions:
- `search_service.py` — kept dev's stricter single-letter / uppercase-2-letter rules but adopted feat's safer `(offset, valid)` parser signature and the token-boundary regex for 3+ letter values; merged bodies manually.
- `test_search_service.py` — kept both dev's tests (RB uppercase, missing offsets) and feat's tests (case-insensitive, ambiguous single-letter, unknown value).
- `EvidenceDetailView.tsx` — kept dev's restructured page (with `initialView="compare"` mode) and the new compare-view integration.
- `EvidenceHighlightText.tsx` — kept dev's tone/category coloring and `findAnchorRange` fallback, added feat's "highlight unavailable" chip (per user's "keep existing component" choice).
- `BilingualComparison.tsx` — extended feat's single-`trace` API with a discriminated union that also accepts the dev API (`detail`, `groupId`, `selectedEvidenceId`, `setSelectedEvidenceId`), so it works in both standalone and compare-mode usage.
- `package.json` — kept vitest per user choice; removed the dev `node --test` test script.
- Docs (lesson, progress, READMEs) — kept dev content and appended a new entry documenting the rebase.

**Verification:**
- All 4 cherry-picked commits applied with new SHAs on `merge/bilingual-comparison-ux-onto-dev`.
- 13 conflicting files resolved without dropping any test cases or feature flags.
- BilingualComparison component now supports both legacy `trace` calls (used by the new test) and dev's compare-mode API.

**Prevention:** When `/executing-plans` targets an existing branch, always inspect that branch's history first to detect pre-existing work. The current `skill:executing-plans` reads the plan file but does not warn about prior implementations of the same plan. A future improvement would be to diff the plan's "Files to Modify" list against the branch's existing commits and prompt the user when a partial implementation already exists.
>>>>>>> 027e8bec (docs(evidence): document bilingual comparison completion)

## 2026-06-12: Chat sidebar hydration mismatch on Next.js App Router static prerender

**Problem**: Console showed `Uncaught Error: Hydration failed because the server rendered HTML didn't match the client` with the diff `+ <li title="Session 8a2b5104..." className="ant-conversations-item ant-conversations-item-active">`. The /chat route is statically prerendered (it appeared as `○ /chat` in `next build` output), and the SSR HTML had no sidebar items because `window.localStorage` is undefined on the server. The first client render then produced the persisted sessions, diverging from the SSR HTML.

**Investigation**: Confirmed via grep that the project has zero `chrome.*`, `window.ai`, `postMessage`, `addEventListener('message')`, `MessageChannel`, or `BroadcastChannel` references in the frontend tree. The earlier `message channel closed` warnings were from Chrome Built-In AI or an extension, not from our code. The new error was a real React hydration failure — its `+` diff line pointed at a specific `<li>` we own, not a generic Chrome internal file.

**Root cause**: `useChatSessions` uses `useState(() => loadLocalChatSessions())` which reads `localStorage` eagerly on first render. In Next.js App Router, this hook runs during the SSR prerender with `localStorage === undefined` and during the first client render with persisted data — producing two different DOM trees. The `<Conversations>` `activeKey` was the most visible symptom (it added the `ant-conversations-item-active` class on the client only), but any localStorage-driven field could have caused it.

**Fix**: Gated the `<Conversations>` JSX on a `mounted` flag set in a one-shot mount effect. First client render matches the SSR HTML (an empty 240px placeholder div with the same width style, so the layout doesn't shift). The effect fires after hydration completes and the second render paints the real sidebar. The `useChatSessions` hook is left untouched — its eager localStorage read is fine once the JSX is gated, because the value is no longer used to produce SSR HTML.

**Lint gotcha**: The `mounted` pattern trips `react-hooks/set-state-in-effect` (a React 19+ rule that warns about cascading renders from `setState` in effects). For this one-shot mount-flag pattern the warning is a false positive: the dep array is empty so the effect runs exactly once, and the rule's suggested alternative (`useSyncExternalStore`) does not apply because the data flows through a TanStack Query / `useState` pipeline, not a raw external store. Suppressed with a per-line `// eslint-disable-line react-hooks/set-state-in-effect` that cites this rationale inline.

**Why not move the localStorage read into the hook**: First attempt (lazy `useState` -> `useEffect` with `setLocalSessions`) preserved behavior but tripped the same lint rule. Second attempt (`useSyncExternalStore`) would have required a custom pub/sub for in-tab updates — overkill. Third attempt (also `useSyncExternalStore` with a no-op subscribe) regressed new-session visibility because the snapshot would not re-read after a `setItem`. The JSX-level gate is the simplest correct fix.

**Prevention**: Any Next.js App Router component that renders values from `localStorage`, `sessionStorage`, or `window.*` must gate the affected JSX on a `mounted` flag, not just gate the data fetch. The data hook can stay eager; the divergence is in the JSX. Document this in the chat feature README so the next person doesn't re-introduce the bug.

**Verification**: 7/7 vitest, 30/30 node --test, 0 ESLint errors on `src/features/chat/`, `tsc --noEmit` clean, `next build` prerenders `/chat` as static content. The original `message channel closed` warnings from Chrome Built-In AI are unrelated and persist (they are external to the app).

---

## 2026-06-12: Migration not applied causing startup errors

**Symptoms**:
1. `SAWarning: The garbage collector is trying to clean up non-checked-in connection` during `_try_startup_lock(engine)`
2. `ProgrammingError: column pipeline_run_states.source_key does not exist` during `recover_orphaned_runs()`

**Root cause**: Migration `2026-06-11_add_pipeline_run_leases.py` (adding `source_key`, `owner_worker_id`, `heartbeat_at` columns) was defined in the model and migration file but never applied to the database. Additionally, `alembic_version.version_num` was `varchar(32)` but the revision ID `2026_06_11_allow_standalone_chat_sessions` is 41 characters, causing a `StringDataRightTruncationError` when attempting to apply migrations.

**Fix**:
1. Altered `alembic_version.version_num` to `varchar(255)` to accommodate long revision IDs
2. Ran `alembic -c database/alembic.ini upgrade head` — all 3 pending migrations applied successfully

**Prevention**: Always apply migrations after creating them. Consider using shorter revision IDs (alembic's auto-generated hashes) instead of full date strings to avoid varchar(32) overflow in the alembic_version table. Alternatively, the initial migration could create `alembic_version.version_num` as varchar(255) instead of the default 32.

## 2026-06-12: Chat UX fixes -- Markdown rendering, sender clear, session delete

**Problem**: From browser QA: (1) LLM assistant replies containing `**bold**`, `` `code` ``, and fenced code blocks rendered as plain text. (2) The sender textarea did not clear after sending a message. (3) Sessions could not be deleted from the sidebar, and session titles showed \"Session {uuid8}\" instead of a recognizable prefix.

**Investigation**: (1) `@ant-design/x` Bubble supports `contentRender`, which overrides the text display with a React component. The `@ant-design/x-markdown` sub-package was not installed. Rather than adding a new dependency, a minimal, dependency-free streaming-safe Markdown renderer was built. (2) The Sender is uncontrolled by default; `@ant-design/x` provides a `SenderRef` with `.clear()` on the inner `TextArea`. (3) `@ant-design/x` Conversations supports a per-item `menu` prop (Ant Design `MenuProps`). The backend has no `DELETE /chat/sessions` endpoint (confirmed: only CRUD GET/POST).

**Fix**:
- **Markdown renderer** (`utils/markdown.tsx`, 150 LOC): Tokenizes lines into blocks (paragraph, fenced code, unordered list) then inline tokens (`**bold**`, `*italic*`, `` `code` ``). Uses React primitives only — NO `dangerouslySetInnerHTML`. Streaming-safe: unclosed `**` at end of string renders as literal. Wired via `contentRender` prop on `bubbleItems` for `role === \"assistant\"`.
- **Sender clear**: Added `useRef<SenderRef>` to both `FullChatView` and `SingleSessionChat`. The new `handleSubmitAndClear` / `handleSingleSessionSubmit` wraps the existing handler logic and calls `finally(() => ref.current?.clear())`, so the input clears even after a failed send (the error toast is still visible).
- **Session title**: Added `sessionLabels` state mapping `sessionId → firstMessage`. Captured in `handleSendMessage` via `captureFirstMessageLabel(sid, content)` which stores the first 5 chars. `conversationItems` uses the label if available, otherwise the default `\"Session {id.slice(0,8)}\"`.
- **Session deletion**: `Conversations` menu prop returns a single \"Delete\" entry with `Modal.confirm`. Calls `removeSession(sessionId)` (which removes from localStorage via `removeLocalChatSession`) and also calls `useXConversations.removeConversation(sessionId)`. If the deleted session was active, switches to the next available session.

**New files**: `utils/markdown.tsx`, `tests/features/chat/ChatMarkdown.test.tsx` (9 vitest tests).
**Modified**: `ChatView.tsx` (+167/-24), `useChatSessions.ts` (+14), `localSessions.ts` (+18), `vitest.config.ts` (+1).

**Prevention**: Any chat backend format change (e.g., adding a new LLM that emits a different Markdown subset) should be reflected in `blockify()` / `tokenizeInline()` in `markdown.tsx`. The 5-char title is a constant `SESSION_TITLE_CHARS` at the top of `ChatView.tsx`.

**Verification**: 16/16 vitest (9 new ChatMarkdown + 7 existing), 30/30 node --test, ESLint clean on `src/features/chat/`, `tsc --noEmit` clean, `next build` prerenders `/chat` as static content.

## 2026-06-12: Log Analysis Fixes — 12 Production Issues Resolved

**Problem**: Production logs (2026-06-01 ~ 2026-06-12) showed ~11,000+ error/warning lines across ~450 log files, covering 13 distinct issues across 4 subsystems.

**Root Causes & Fixes**:

| # | Issue | Root Cause | Fix |
|---|---|---|---|
| 1 | Duplicate track warnings (~8,500+) | No dedup on `(field_id, track)` | Post-query dedup by `updated_at` + warning→DEBUG |
| 2 | Redis connection spam (~370+) | WARNING log level for non-critical service | Downgraded to DEBUG in health.py + main.py |
| 3 | Orphan recovery fails (~47) | Migration not applied | Already at head — verified |
| 4 | Ellipsis snippet not found (~200+) | Exact match fails on `...` fragments | `_fuzzy_ellipsis_match()` with sequential fragment search |
| 5 | HTML response from LLM (~18) | No HTML detection | `_is_html()` regex + early return in formatter |
| 6 | OPENAI_API_KEY missing (~50) | Config wiring gap | Diagnostic — vault file needs credentials |
| 7 | Connection pool leak (~49) | `raw_conn` not closed on SQL error | Nested try-except in `_try_startup_lock` |
| 8 | context_type rejects sections (~37) | Literal missing academic types | Extended Literal + `_map_block_type` update |
| 9 | FileNotFoundError retried (~30) | `OSError` in `_RETRYABLE_ERRORS` catches subclasses | `_PERMANENT_OS_ERRORS` before `_RETRYABLE_ERRORS` in all 3 adapters |
| 10 | Phase4ServiceFactory close (~70) | WARNING log on shutdown | Downgraded to DEBUG + None guard |
| 11 | Semantic matching fails (~40) | Model server not running | Diagnostic — server is running, endpoints verified |
| 12 | Translation validation false positive (~8) | Short text similarity threshold too aggressive | Skip unchanged check for `len(source) < 100` |

**Key Lessons**:

1. **Python exception ordering matters**: `except OSError` catches `FileNotFoundError`, `PermissionError`, etc. When adding permanent-error exclusions, the specific exception must come BEFORE the general one in the except chain.

2. **`in` operator checks identity, not subclass**: `FileNotFoundError not in (OSError,)` returns `True` because `in` checks exact class identity. The real catch happens at runtime via `except OSError`.

3. **Ellipsis in LLM snippets requires fragment matching**: Simple substring search fails when `...` represents omitted text. Split on ellipsis and verify each fragment appears in document order.

4. **Short technical texts inflate similarity**: Gene names, mutation notation (e.g., `c.5266dupC`, `p.Gln1756ProfsTer74`) are shared between source and translation. Minimum length guards prevent false positives.

5. **Non-critical service failures should log at DEBUG**: Redis, model-server, and shutdown cleanup failures generate log spam when logged at WARNING. DEBUG level preserves debuggability without noise.

6. **Cargo.lock must be synced across worktrees**: Dependency version mismatches (e.g., `aws-smithy-types`) cause compilation failures in worktrees. Always sync lockfiles after creating a worktree.

7. **Mock setup for `await engine.raw_connection()`**: `MagicMock.raw_connection` returns a value that is then awaited. Use `AsyncMock(return_value=mock_conn)` so `await engine.raw_connection()` returns `mock_conn` directly.

**Files Changed**:
- `backend/app/main.py` — connection leak fix, Redis log downgrade, shutdown cleanup
- `backend/src/utils/health.py` — Redis health check log downgrade
- `backend/src/core/.../extract_evidence/core.py` — fuzzy ellipsis match, context types
- `backend/src/core/.../extract_evidence/contracts.py` — extended context_type Literal
- `backend/src/core/.../format/formatter.py` — HTML detection
- `backend/src/core/.../translate/validator/core.py` — short text threshold
- `backend/src/core/.../search_service.py` — track deduplication
- `backend/src/agents/phase_{1,2,3}_adapter.py` — permanent OS error exclusion
- 8 new test files with 23 tests total

**Verification**: All 23 new tests pass. All 16 existing search_service tests pass. Full test suite passes (except pre-existing `test_download_with_doi_fallback` failure unrelated to changes).
