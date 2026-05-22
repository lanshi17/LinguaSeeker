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
