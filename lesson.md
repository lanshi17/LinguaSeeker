# Lesson Log

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
