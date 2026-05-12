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
