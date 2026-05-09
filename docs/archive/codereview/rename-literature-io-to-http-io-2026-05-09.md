# Code Review: Rename literature-io → http-io + Add MinerU API Support

**Branch:** `feature/rename-literature-io-to-http-io-and-add-mineru`
**Reviewer:** AI Code Review
**Date:** 2026-05-09
**Files changed:** 24 (556 insertions, 52 deletions)
**Verification:** `cargo test` (http-io: 23/23 passed), `cargo check` (rust-io: OK)

---

## Executive Summary

The rename is clean and well-executed. All critical paths — Rust facade (`rust-io/src/lib.rs`), Python callers (`gateway.py`, `base.py`), crate metadata (`Cargo.toml`), and documentation (`README.md`, `AGENTS.md`) — are consistently updated. The MinerU integration is functionally complete with 4 new async Python functions exposed through `rust_io.http`.

One **blocking** documentation issue remains: the facade README (`backend/libs/rust-io/README.md`) was not updated and still describes the old `rust_io.literature` architecture. Additionally, several `docs/active/` files still reference the old `literature-io` crate name.

---

## Part A: Rename Review (Tasks 1–4)

### ✅ Task 1: Crate directory rename and Cargo.toml
- `backend/libs/literature-io/` → `backend/libs/http-io/` — done via `git mv`
- `http-io/Cargo.toml`: `name = "http-io"`, `lib.name = "http_io"`, `crate-type = ["rlib"]` — correct
- `rust-io/Cargo.toml`: `http-io = { path = "../http-io" }` — correct
- All provider source files preserved unchanged under `http-io/src/providers/`

### ✅ Task 2: Rust facade (`rust-io/src/lib.rs`)
- Python submodule renamed from `"literature"` → `"http"`
- `register_submodule` call updated from `"rust_io.literature"` → `"rust_io.http"`
- All `wrap_pyfunction!` calls use `http_io::py::*` — correct
- MinerU functions (`mineru_create_task`, `mineru_get_result`, `mineru_batch_submit`, `mineru_batch_result`) registered — correct
- `files` submodule unchanged — correct

### ✅ Task 3: Python imports
- `gateway.py`: `import rust_io.http as http_io`, all call sites and docstrings updated — correct
- `web/base.py`: both import sites (`extract_pdf_links`, `scrape_html`) updated — correct
- `__init__.py`: docstring updated from `literature_io` → `http-io` — correct

### ⚠️ Task 3: Test file incomplete update

**`backend/tests/core/ingest_and_digitize_data/document_acquisition/online_acquisition/test_gateway.py`**

| Line | Issue |
|------|-------|
| 90 | Function name `test_literature_io_not_available` — stale, should be `test_http_io_not_available` |
| 91 | `ImportError("no literature_io")` — stale error message |

The mock patches `builtins.__import__` with `side_effect=ImportError`, so the exact error message doesn't break functionality. However, the stale naming is confusing for maintainers.

### 🔴 Task 4: Facade README not updated

**`backend/libs/rust-io/README.md`** — **completely stale**

| Line | Current (wrong) | Expected |
|------|-----------------|----------|
| 3 | `Registers rust_io.files and rust_io.literature submodules` | `Registers rust_io.files and rust_io.http submodules` |
| 7 | `import rust_io.literature as literature` | `import rust_io.http as http_io` |
| 10 | `await literature.fetch_one(...)` | `await http_io.fetch_one(...)` |
| 33 | `literature-io (rlib)` | `http-io (rlib)` |
| 37 | Sub-crate link to `literature-io/` | Should link to `http-io/` |
| 39-46 | Exports table title `rust_io.literature` | Should be `rust_io.http` |
| 71 | Sub-crate docs link `literature-io/` | Should be `http-io/` |
| Missing | No MinerU functions in exports table | Should list `mineru_create_task`, `mineru_get_result`, `mineru_batch_submit`, `mineru_batch_result` |

### ✅ Task 4: http-io README
- `backend/libs/http-io/README.md` — fully updated with correct crate name, Python API, module structure, MinerU docs, and call chain diagram.

### ✅ Task 4: AGENTS.md
- Line 263: Table row updated from `literature-io` → `http-io`, description includes MinerU
- Line 265: Gateway description updated to reference `http_io.fetch_one()`
- Line 349: `cd backend/libs/rust-io # or files-io, http-io` — correct

---

## Part B: MinerU Implementation Review (Tasks 5–7)

### ✅ Task 5: MinerU types (`types.rs`)

Three request structs implemented:
- `MinerUCreateTaskRequest` — 10 optional fields + mandatory `url`
- `MinerUBatchFileEntry` — 1 mandatory + 3 optional fields
- `MinerUBatchSubmitRequest` — wraps `Vec<MinerUBatchFileEntry>` + batch-level options

**Plan-implementation divergence:** The plan specified `MinerUModelVersion` enum, `MinerUTaskState` enum, and `MinerUExtractProgress` struct as strongly-typed response types. The implementation simplified `model_version` to `Option<String>` and omitted response types entirely — all MinerU functions return `serde_json::Value`. This is a pragmatic choice: the MinerU API response shape is not guaranteed stable, and `Value` avoids deserialization failures from API changes. The plan's "strongly-typed request/response structs" claim should be revised to reflect the actual implementation.

### ✅ Task 6: MinerU client module (`mineru.rs`)

- Four async functions: `create_task`, `get_result`, `batch_submit`, `batch_result`
- Two body builders: `build_create_task_body`, `build_batch_submit_body` — correct conditional inclusion of optional fields
- Two auth-aware HTTP helpers: `post_json_with_auth`, `get_with_auth` — thin wrappers, clean
- `MINERU_BASE_URL` as constant — correct
- Authorization: `Bearer {token}` — standard, correct
- **Tests:** 4 unit tests for body builders, including edge case for `MinerU-HTML` model version and empty defaults — good coverage of the serialization logic

**Minor concerns:**
- No HTTP-layer tests (mock `HttpClient`). The body builders are tested, but the actual API flow (`create_task` → `post_json_with_auth`) is not — this is acceptable for an integration boundary but noted.
- `build_create_task_body` and `build_batch_submit_body` have near-identical conditional field logic. A shared helper for `Option`-to-`Value` conditional insertion could reduce duplication (~30 duplicated lines).

### ✅ Task 7: MinerU Python bindings (`py.rs`)

Four `#[pyfunction]`s:
- `mineru_create_task` — 14 parameters, constructs `MinerUCreateTaskRequest`, delegates to `mineru::create_task`
- `mineru_get_result` — 4 parameters, delegates to `mineru::get_result`
- `mineru_batch_submit` — 11 parameters + `files: Vec<PyDict>`, parses file entries from Python dicts, constructs `MinerUBatchSubmitRequest`
- `mineru_batch_result` — 4 parameters, delegates to `mineru::batch_result`

All use `pyo3_async_runtimes::tokio::future_into_py` for async → Python coroutine conversion. Error propagation: `GatewayError` → `PyErr` via existing `From` impl. Result serialization: `pythonize::pythonize` → `unbind()`.

**Correct decisions:**
- `max_retries` is hardcoded to `None` for MinerU calls — correct, since POST operations (create/batch_submit) must not auto-retry
- `timeout_ms` and `proxy` are accepted and passed through — correct
- `files` parameter parsed with proper error handling for missing `url` key

### ✅ Task 8: Build verification
- `cargo test` in `http-io`: 23 passed (2 suites) — all existing provider tests + new MinerU tests
- `cargo check` in `rust-io`: OK — facade compiles with new MinerU registrations

---

## Documentation Debt (docs/active/)

The following `docs/active/` files still reference `literature-io` and should be updated:

| File | Lines | Content |
|------|-------|---------|
| `BACKEND_STRUCTURE.md` | 136 | `└── literature-io/` in directory tree |
| `TECH_STACK.md` | 67, 81 | `literature-io/` directory and `literature-io` crate table row |
| `IMPLEMENTATION_PLAN.md` | 54 | `rust_io integrates literature_io` in phase description |

These are specification documents (not generated docs), so stale references are documentation debt but not a functional concern. The `docs/codereview/` and `docs/archive/` directories contain historical review artifacts that correctly refer to `literature-io` (they document the pre-rename state) and should NOT be modified.

---

## Summary of Findings

| Severity | Count | Items |
|----------|-------|-------|
| 🔴 Blocking | 1 | `rust-io/README.md` completely stale |
| 🟡 High | 3 | `test_gateway.py` stale test name/msg; `docs/active/` stale references; plan-implementation divergence on response types |
| 🔵 Medium | 2 | No MinerU HTTP mock tests; body builder code duplication |
| ⚪ Low | 0 | — |

### Recommendation

**Must fix before merge:**
1. Update `backend/libs/rust-io/README.md` to reflect `rust_io.http`, `http-io`, and list MinerU exports.

**Should fix before merge:**
2. Update `test_gateway.py` function name `test_literature_io_not_available` and associated `ImportError` message.
3. Update `docs/active/BACKEND_STRUCTURE.md`, `TECH_STACK.md`, `IMPLEMENTATION_PLAN.md` to reference `http-io` instead of `literature-io`.
4. Update the plan document to note that MinerU response types are `serde_json::Value` (not strongly-typed structs), or add the missing response structs.

**Can defer:**
5. Add HTTP mock tests for MinerU API functions.
6. Extract shared `Option`-to-`Value` conditional field logic from body builders.

---

## Test Results

```
backend/libs/http-io $ cargo test
running 19 tests (providers, scraper, client, error) ... ok
running 4 tests (mineru body builders) ... ok

Result: 23 passed, 0 failed
```

```
backend/libs/rust-io $ cargo check
    Checking rust-io v0.1.0
    Finished `dev` profile [unoptimized + debuginfo] target(s)
OK
```
