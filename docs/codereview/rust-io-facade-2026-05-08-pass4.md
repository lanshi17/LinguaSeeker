# Code Review: refactor/rust-io-facade (Pass 4)

- **Branch**: `refactor/rust-io-facade`
- **Date**: 2026-05-08
- **Reviewer**: Hephaestus (AI)
- **Scope**: Worktree `/data/[redacted-user]/Projects/01_ACMG_Lingua_rust_io_refactor`
- **Pass**: Fourth review after compatibility and security follow-up changes
- **Previous reports**:
  - `docs/codereview/rust-io-facade-2026-05-08.md`
  - `docs/codereview/rust-io-facade-2026-05-08-pass3.md`

---

## Summary Decision

🔄 **Request changes** before merge.

The main facade direction is sound: `rust_io` now registers `rust_io.files` and `rust_io.literature`, legacy file helper functions are restored through `files_io::py::utils`, archive extraction has explicit traversal/symlink hardening, error mapping is more precise, and `fetch_multi` now returns per-provider failures instead of aborting on the first error.

However, the current branch still contains packaging and behavior risks that can break CI or surprise callers. The most important remaining issue is that `literature-io` is documented and implemented as `rlib`-only but still contains standalone Python packaging artifacts and a generated wheel CI workflow.

---

## Review Inputs and Verification Notes

### Checked directly

- Branch/worktree status: `refactor/rust-io-facade`
- Changed-file diff/stat for the worktree
- Key Rust files under:
  - `backend/libs/rust-io/`
  - `backend/libs/files-io/`
  - `backend/libs/literature-io/`
- Existing reports under `docs/codereview/`
- `git diff --check`: clean

### Background agent status

Four requested background review agents were launched for exhaustive review, but all failed immediately because the API key status was inactive. Their failure outputs were collected and no findings were available from them. This report is therefore based on direct source/diff review.

---

## Strengths Since Earlier Passes

🎉 **Facade compatibility improved.** `backend/libs/rust-io/src/lib.rs` now registers both `rust_io.files` and `rust_io.literature` in `sys.modules`, and re-exports the legacy helpers `compute_sha256`, `write_file`, and `validate_pdf_magic` via `files_io::py::utils`.

🎉 **Archive extraction hardening landed.** `zip.rs` rejects symlink entries and validates existing path components against the canonical output root. `tar_gz.rs` rejects symlinks and hardlinks before unpacking.

🎉 **Provider fan-out behavior improved.** `literature-io/src/py.rs` now uses `futures::future::join_all` for `fetch_multi` and returns `FetchResult::failure(...)` per failed provider, which is better for multi-provider search resilience.

🎉 **Several previous report items are fixed.** The stale `rust-io` dependencies `serde_json` and `pythonize` are removed, `S3Backend` uses `is_truncated()`, `HttpClient::Default` is gone, retry backoff is capped, Crossref DOI path segments are encoded, and Python-side error classes are more specific.

---

## Findings

### 🔴 [blocking] `literature-io` still ships standalone Python packaging artifacts despite being `rlib`-only

**Files**:

- `backend/libs/literature-io/pyproject.toml`
- `backend/libs/literature-io/.github/workflows/CI.yml`
- `backend/libs/literature-io/uv.lock`

`backend/libs/literature-io/README.md` correctly says this crate is **not a standalone Python module** and must be accessed through `rust_io.literature`. Its `Cargo.toml` also has:

```toml
[lib]
name = "literature_io"
crate-type = ["rlib"]
```

But the branch still adds maturin packaging for `literature-io` itself:

```toml
[build-system]
requires = ["maturin>=1.13,<2.0"]
build-backend = "maturin"

[project]
name = "literature-io"
```

and a generated GitHub workflow that runs `maturin-action` to build wheels for that crate. Because the crate has no `cdylib` Python extension entry point, this packaging path is inconsistent with the new architecture and is likely to fail or produce an unusable package if invoked.

**Why it matters**: This undermines the facade refactor by leaving a second, contradictory distribution path. Future maintainers or CI jobs may try to publish/build `literature-io` as a Python module even though the only valid Python module should be `rust_io`.

**Recommendation**: Delete standalone Python packaging artifacts from `backend/libs/literature-io/` unless there is an explicit plan to restore `cdylib`/`#[pymodule]`. Keep Python packaging only in the facade crate (`backend/libs/rust-io`). If Rust-only CI is needed for `literature-io`, replace the generated maturin workflow with `cargo check` / `cargo test` documentation or workflow steps.

---

### 🟡 [important] `fetch_multi` converts unknown provider/action errors into successful Python awaits

**File**: `backend/libs/literature-io/src/py.rs:54-67`

```rust
let tasks = providers.into_iter().map(|provider| {
    let client = client.clone();
    let action = action.clone();
    let params = params.clone();
    async move {
        match execute_provider(&client, &provider, &action, &params).await {
            Ok(result) => result,
            Err(err) => FetchResult::failure(&provider, vec![err.to_string()]),
        }
    }
});
```

This is good for transient provider failures, but it also swallows programmer errors such as an unsupported provider name or an unsupported action/provider combination. The new regression test explicitly expects unknown providers to return normal failure objects.

**Why it matters**: Python callers may treat a successful coroutine as a valid multi-provider response even when every provider name is misspelled. That can hide integration bugs that should fail loudly.

**Recommendation**: Split validation errors from runtime provider failures. For example, validate all provider/action pairs before launching requests and raise `ValueError` for unsupported providers/actions, while still returning per-provider `FetchResult::failure` for HTTP/provider runtime failures. If soft-failure for unknown providers is intentional, document it in `literature-io/README.md` as part of the Python API contract.

---

### 🟡 [important] `batch_copy_async` still executes the whole batch sequentially inside one blocking task

**File**: `backend/libs/files-io/src/py/parallel.rs:139-169`

```rust
pyo3_async_runtimes::tokio::future_into_py(py, async move {
    let result = tokio::task::spawn_blocking(move || {
        Python::attach(|py| {
            batch_copy(py, sources, destinations, access_key, secret_key, endpoint, region)
        })
    })
    .await
    .map_err(FileError::TaskJoin)??;
    Ok(result)
})
```

Despite the function name, this only moves the existing sequential `batch_copy` loop onto a blocking thread. It does not copy multiple files concurrently.

**Why it matters**: The public name implies parallel/asynchronous batch work, but S3 or large local copies still run one-by-one. Callers may overestimate throughput or use it in latency-sensitive flows expecting parallelism.

**Recommendation**: Either rename/document it as non-blocking sequential batch copy, or implement bounded concurrency (for example with `tokio::task::spawn_blocking` per local copy and a semaphore/concurrency limit). If true parallelism is deferred, note that clearly in README/API docs.

---

### 🟡 [important] `S3Backend::read_chunk` underflows when `size == 0`

**File**: `backend/libs/files-io/src/backends/s3.rs:85-87`

```rust
fn read_chunk(&self, path: &str, offset: u64, size: u64) -> Result<Vec<u8>, FileError> {
    let (bucket, key) = parse_s3_path(path)?;
    let range = format!("bytes={}-{}", offset, offset + size - 1);
```

If `size` is zero, `offset + size - 1` underflows in debug builds and creates an invalid range in release builds.

**Why it matters**: Python exposes `File.read_chunk(offset, size)`, so a caller can trigger this with `size=0`. Local and S3 behavior should be well-defined for empty reads.

**Recommendation**: Return `Ok(Vec::new())` when `size == 0`, and use checked or saturating addition for `offset + size - 1` to avoid overflow on very large inputs.

---

### 🟢 [nit] Reviewer identity in older reports is inconsistent

**Files**:

- `docs/codereview/rust-io-facade-2026-05-08.md`
- `docs/codereview/rust-io-facade-2026-05-08-pass3.md`

Older reports list `Sisyphus (AI)` as reviewer, while this session identity is `Hephaestus`. This is not a code issue, but it can confuse audit trails.

**Recommendation**: If these reports are kept as permanent artifacts, consider adding a small note that they were generated by previous agent passes, and use consistent reviewer naming going forward.

---

## Previous Finding Status Snapshot

| Earlier finding | Current status |
|---|---|
| Missing legacy helpers in `rust_io.files` | ✅ Fixed via `files_io::py::utils` and facade re-export |
| `files-io/tests/test_files_io.py` importing removed `files_io` module | ✅ Fixed to `import rust_io.files as files_io` |
| Zip/tar symlink traversal risk | ✅ Addressed with symlink/hardlink rejection and canonical path checks |
| `HttpClient::Default` panic | ✅ Removed |
| `fetch_multi` sequential fan-out | ✅ Parallelized with `join_all` |
| Unpaywall fallback `[redacted-email]` | ✅ Replaced by `unpaywall_requires_email` failure |
| Crossref DOI not URL-encoded | ✅ Fixed |
| OpenAlex DOI filter encoding concern | ✅ `HttpClient::build_url` encodes query parameter values; test covers this |
| Error type information lost at Python boundary | ✅ Improved for both `GatewayError` and `FileError` |
| Unused `rust-io` dependencies | ✅ Removed from `backend/libs/rust-io/Cargo.toml` |

---

## Suggested Verification Before Merge

Run these after addressing the blocking packaging issue:

```bash
cd backend/libs/rust-io
cargo test

cd ../files-io
cargo test

cd ../literature-io
cargo test

cd ../../
uv run maturin develop --release -m libs/rust-io/Cargo.toml
uv run pytest tests/core/ingest_and_digitize_data/test_rust_io_facade.py libs/files-io/tests/test_files_io.py
```

If `literature-io/.github/workflows/CI.yml` is removed, verify there is no remaining documentation instructing maintainers to build `literature-io` as a standalone Python wheel.
