# rust-io Facade Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Consolidate `files-io` and `literature-io` as Rust library dependencies of `rust-io`, making `rust-io` the single PyO3 entry point that `src/` imports from.

**Architecture:** `files-io` and `literature-io` become pure Rust libraries (rlib only). `rust-io` depends on both via Cargo path dependencies and re-exports their PyO3 functions under `rust_io.files.*` and `rust_io.literature.*` submodules. `src/` only does `import rust_io`.

**Tech Stack:** Rust (PyO3 0.28, maturin), Python 3.12, uv

---

## Current State Analysis

| Module | Python import | Crate type | Installable | Used by src/ |
|---|---|---|---|---|
| `libs/rust-io/` | `rust_io` | cdylib + rlib | No pyproject.toml | No |
| `libs/files-io/` | `files_io` | cdylib + rlib | Yes (pyproject.toml) | Yes (`user_upload/service.py`) |
| `libs/literature-io/` | `literature_io` | cdylib + rlib | Yes (pyproject.toml) | Yes (`gateway.py`, `web/base.py`) |

**Problem:** `rust-io` contains 100% duplicated code from `literature-io` (providers, client, scraper, types, error) plus a small `files` module that's a subset of `files-io`. Nobody imports `rust_io` from `src/`.

## Target State

```
src/ ──import──> rust_io (single cdylib)
                   ├── rust_io.literature.*  (delegates to literature-io rlib)
                   └── rust_io.files.*       (delegates to files-io rlib)
```

---

### Task 1: Convert files-io to rlib-only

**Files:**
- Modify: `libs/files-io/Cargo.toml:8-9`
- Modify: `libs/files-io/src/lib.rs`

**Step 1: Remove cdylib and pymodule from files-io**

In `libs/files-io/Cargo.toml`, change crate-type to rlib only:

```toml
[lib]
name = "files_io"
crate-type = ["rlib"]
```

Remove the `pyo3/extension-module` feature from dependencies (keep pyo3 itself since structs use `#[pyclass]`).

**Step 2: Make lib.rs expose public modules instead of pymodule**

In `libs/files-io/src/lib.rs`, replace the `#[pymodule]` function with public module exports:

```rust
pub mod error;
pub mod hash;
pub mod backends;
pub mod archive;
pub mod py;
```

**Step 3: Verify files-io compiles as rlib**

Run: `cd libs/files-io && cargo check`
Expected: compiles without errors

**Step 4: Commit**

```bash
git add libs/files-io/Cargo.toml libs/files-io/src/lib.rs
git commit -m "refactor(files-io): convert to rlib-only, remove pymodule entry point"
```

---

### Task 2: Convert literature-io to rlib-only

**Files:**
- Modify: `libs/literature-io/Cargo.toml:8-9`
- Modify: `libs/literature-io/src/lib.rs`

**Step 1: Remove cdylib and pymodule from literature-io**

In `libs/literature-io/Cargo.toml`, change crate-type to rlib only:

```toml
[lib]
name = "literature_io"
crate-type = ["rlib"]
```

**Step 2: Make lib.rs expose public modules instead of pymodule**

In `libs/literature-io/src/lib.rs`, replace the `#[pymodule]` function with public module exports:

```rust
pub mod error;
pub mod types;
pub mod client;
pub mod providers;
pub mod scraper;
pub mod py;
```

**Step 3: Verify literature-io compiles as rlib**

Run: `cd libs/literature-io && cargo check`
Expected: compiles without errors

**Step 4: Commit**

```bash
git add libs/literature-io/Cargo.toml libs/literature-io/src/lib.rs
git commit -m "refactor(literature-io): convert to rlib-only, remove pymodule entry point"
```

---

### Task 3: Add files-io and literature-io as dependencies of rust-io

**Files:**
- Modify: `libs/rust-io/Cargo.toml`

**Step 1: Add path dependencies**

In `libs/rust-io/Cargo.toml`, add:

```toml
[dependencies]
# ... existing deps ...
files-io = { path = "../files-io" }
literature-io = { path = "../literature-io" }
```

Remove duplicate dependencies that are already transitively provided by files-io and literature-io (reqwest, scraper, sha2, url, urlencoding — keep only if rust-io uses them directly).

**Step 2: Verify rust-io compiles with new dependencies**

Run: `cd libs/rust-io && cargo check`
Expected: compiles without errors

**Step 3: Commit**

```bash
git add libs/rust-io/Cargo.toml
git commit -m "refactor(rust-io): add files-io and literature-io as path dependencies"
```

---

### Task 4: Rewrite rust-io lib.rs as facade

**Files:**
- Modify: `libs/rust-io/src/lib.rs`
- Delete: `libs/rust-io/src/py.rs` (replaced by literature-io's py module)
- Delete: `libs/rust-io/src/files.rs` (replaced by files-io)
- Delete: `libs/rust-io/src/client.rs` (duplicate of literature-io)
- Delete: `libs/rust-io/src/scraper.rs` (duplicate of literature-io)
- Delete: `libs/rust-io/src/types.rs` (duplicate of literature-io)
- Delete: `libs/rust-io/src/error.rs` (duplicate of literature-io)
- Delete: `libs/rust-io/src/providers/` (entire directory, duplicate of literature-io)

**Step 1: Rewrite lib.rs as facade**

Replace `libs/rust-io/src/lib.rs` with:

```rust
use pyo3::prelude::*;

#[pymodule]
fn rust_io(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // ── literature submodule ──
    let literature = PyModule::new(m.py(), "literature")?;
    literature.add_function(wrap_pyfunction!(
        literature_io::py::fetch_one, &literature
    )?)?;
    literature.add_function(wrap_pyfunction!(
        literature_io::py::fetch_multi, &literature
    )?)?;
    literature.add_function(wrap_pyfunction!(
        literature_io::py::scrape_web, &literature
    )?)?;
    literature.add_function(wrap_pyfunction!(
        literature_io::py::scrape_html, &literature
    )?)?;
    literature.add_function(wrap_pyfunction!(
        literature_io::py::extract_pdf_links, &literature
    )?)?;
    m.add_submodule(&literature)?;

    // ── files submodule ──
    let files = PyModule::new(m.py(), "files")?;
    files.add_class::<files_io::py::file::File>()?;
    files.add_function(wrap_pyfunction!(
        files_io::py::parallel::batch_copy, &files
    )?)?;
    files.add_function(wrap_pyfunction!(
        files_io::py::parallel::batch_compress, &files
    )?)?;
    files.add_function(wrap_pyfunction!(
        files_io::py::parallel::batch_copy_async, &files
    )?)?;
    files.add_function(wrap_pyfunction!(
        files_io::py::dedup::check_duplicate, &files
    )?)?;
    files.add_function(wrap_pyfunction!(
        files_io::py::dedup::batch_hash, &files
    )?)?;
    m.add_submodule(&files)?;

    Ok(())
}
```

**Step 2: Delete duplicate source files**

```bash
rm libs/rust-io/src/py.rs
rm libs/rust-io/src/files.rs
rm libs/rust-io/src/client.rs
rm libs/rust-io/src/scraper.rs
rm libs/rust-io/src/types.rs
rm libs/rust-io/src/error.rs
rm -rf libs/rust-io/src/providers/
```

**Step 3: Verify compilation**

Run: `cd libs/rust-io && cargo check`
Expected: compiles without errors. If `pyo3::prelude::*` functions like `wrap_pyfunction!` need the sub-crates' functions to be `pub`, adjust visibility in files-io/literature-io accordingly.

**Step 4: Commit**

```bash
git add -A libs/rust-io/src/
git commit -m "refactor(rust-io): replace duplicate code with facade delegating to files-io and literature-io"
```

---

### Task 5: Add pyproject.toml to rust-io

**Files:**
- Create: `libs/rust-io/pyproject.toml`

**Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["maturin>=1.13,<2.0"]
build-backend = "maturin"

[project]
name = "rust-io"
requires-python = ">=3.12"
classifiers = [
    "Programming Language :: Rust",
    "Programming Language :: Python :: Implementation :: CPython",
]
dynamic = ["version"]

[tool.maturin]
features = ["pyo3/extension-module"]
```

**Step 2: Verify maturin build**

Run: `cd libs/rust-io && uv run maturin develop --release`
Expected: builds and installs `rust_io` Python package

**Step 3: Commit**

```bash
git add libs/rust-io/pyproject.toml
git commit -m "feat(rust-io): add pyproject.toml for Python package installation"
```

---

### Task 6: Update backend pyproject.toml to depend on rust-io

**Files:**
- Modify: `backend/pyproject.toml`

**Step 1: Replace files-io dependency with rust-io**

In `backend/pyproject.toml`:
- Change `"files-io",` to `"rust-io",` in `[project.dependencies]`
- Change `[tool.uv.sources]` from `files-io = { path = "libs/files-io", editable = true }` to `rust-io = { path = "libs/rust-io", editable = true }`

**Step 2: Install updated dependencies**

Run: `cd backend && uv pip install -e ".[dev]"`
Expected: installs `rust_io` package

**Step 3: Verify import works**

Run: `cd backend && uv run python -c "import rust_io; print(dir(rust_io)); print(dir(rust_io.literature)); print(dir(rust_io.files))"`
Expected: shows all expected functions

**Step 4: Commit**

```bash
git add backend/pyproject.toml
git commit -m "chore(backend): switch dependency from files-io to rust-io"
```

---

### Task 7: Update src/ imports from files_io/literature_io to rust_io

**Files:**
- Modify: `src/core/ingest_and_digitize_data/literature_acquisition/gateway.py:197`
- Modify: `src/core/ingest_and_digitize_data/literature_acquisition/web/base.py:40-41,64-65`
- Modify: `src/core/ingest_and_digitize_data/user_upload/service.py:21-23`

**Step 1: Update gateway.py**

In `gateway.py:197`, change:
```python
import literature_io
```
to:
```python
import rust_io.literature as literature_io
```

**Step 2: Update web/base.py**

In `web/base.py:40-41`, change:
```python
import literature_io
return literature_io.extract_pdf_links(html, base_url)
```
to:
```python
import rust_io.literature as literature_io
return literature_io.extract_pdf_links(html, base_url)
```

In `web/base.py:64-65`, change:
```python
import literature_io
return literature_io.scrape_html(html, css_selector)
```
to:
```python
import rust_io.literature as literature_io
return literature_io.scrape_html(html, css_selector)
```

**Step 3: Update user_upload/service.py**

In `service.py:21-23`, change:
```python
try:
    import files_io
except ImportError:
    files_io = None
```
to:
```python
try:
    import rust_io.files as files_io
except ImportError:
    files_io = None
```

**Step 4: Commit**

```bash
git add src/core/ingest_and_digitize_data/literature_acquisition/gateway.py \
        src/core/ingest_and_digitize_data/literature_acquisition/web/base.py \
        src/core/ingest_and_digitize_data/user_upload/service.py
git commit -m "refactor(src): import from rust_io facade instead of files_io/literature_io"
```

---

### Task 8: Update tests

**Files:**
- Modify: `tests/core/ingest_and_digitize_data/literature_acquisition/test_gateway.py`

**Step 1: Update mock patch paths**

In `test_gateway.py:91`, the mock patches `builtins.__import__`. Update to mock `rust_io.literature` instead of `literature_io`:

```python
@pytest.mark.asyncio
async def test_literature_io_not_available(self):
    with patch("builtins.__import__", side_effect=ImportError("no rust_io")):
        result = await call_provider(GatewayRequest(provider="crossref"))
        assert result.success is False
        assert "not available" in result.warnings[0]
```

**Step 2: Run tests**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/literature_acquisition/test_gateway.py -v`
Expected: all tests pass

**Step 3: Commit**

```bash
git add tests/core/ingest_and_digitize_data/literature_acquisition/test_gateway.py
git commit -m "test: update gateway tests for rust_io facade imports"
```

---

### Task 9: Clean up old standalone packages

**Files:**
- Delete: `libs/files-io/pyproject.toml` (no longer installable standalone)
- Delete: `libs/literature-io/pyproject.toml` (no longer installable standalone)
- Delete: `libs/files-io/uv.lock` (no longer needed)
- Delete: `libs/literature-io/uv.lock` (no longer needed)

**Step 1: Remove standalone Python package configs**

```bash
rm libs/files-io/pyproject.toml libs/files-io/uv.lock
rm libs/literature-io/pyproject.toml libs/literature-io/uv.lock
```

**Step 2: Verify full build still works**

Run: `cd libs/rust-io && cargo build --release`
Expected: builds successfully

**Step 3: Commit**

```bash
git add -A libs/files-io/ libs/literature-io/
git commit -m "chore: remove standalone pyproject.toml from files-io and literature-io"
```

---

### Task 10: Verify end-to-end

**Step 1: Full cargo test**

Run: `cd libs/rust-io && cargo test`
Expected: all tests pass

**Step 2: Full pytest**

Run: `cd backend && uv run pytest -v`
Expected: all tests pass

**Step 3: Verify import structure**

Run:
```bash
cd backend && uv run python -c "
import rust_io
# literature submodule
assert hasattr(rust_io.literature, 'fetch_one')
assert hasattr(rust_io.literature, 'fetch_multi')
assert hasattr(rust_io.literature, 'scrape_web')
assert hasattr(rust_io.literature, 'scrape_html')
assert hasattr(rust_io.literature, 'extract_pdf_links')
# files submodule
assert hasattr(rust_io.files, 'File')
assert hasattr(rust_io.files, 'batch_copy')
assert hasattr(rust_io.files, 'batch_compress')
assert hasattr(rust_io.files, 'batch_copy_async')
assert hasattr(rust_io.files, 'check_duplicate')
assert hasattr(rust_io.files, 'batch_hash')
print('All assertions passed')
"
```

Expected: `All assertions passed`

---

## Final Directory Structure

```
libs/
├── rust-io/                    # Single installable PyO3 package
│   ├── Cargo.toml              # depends on files-io + literature-io
│   ├── Cargo.lock
│   ├── pyproject.toml          # NEW — makes it pip-installable
│   └── src/
│       └── lib.rs              # Facade — #[pymodule] delegates to sub-crates
├── files-io/                   # Pure Rust library (rlib)
│   ├── Cargo.toml              # cdylib removed
│   ├── Cargo.lock
│   └── src/
│       ├── lib.rs              # pub mod exports
│       ├── error.rs
│       ├── hash.rs
│       ├── backends/
│       ├── archive/
│       └── py/
└── literature-io/              # Pure Rust library (rlib)
    ├── Cargo.toml              # cdylib removed
    ├── Cargo.lock
    └── src/
        ├── lib.rs              # pub mod exports
        ├── error.rs
        ├── types.rs
        ├── client.rs
        ├── providers/
        ├── scraper.rs
        └── py/
```

## Rollback Plan

If any step fails, revert with `git checkout HEAD~1`. Each commit is atomic and self-contained.
