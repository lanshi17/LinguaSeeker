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
