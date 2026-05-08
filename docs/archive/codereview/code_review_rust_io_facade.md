# Code Review: refactor/rust-io-facade

**Date:** 2026-05-08  
**Branch:** refactor/rust-io-facade  
**Reviewer:** Sisyphus AI

---

## 📋 Overview

This refactor splits the monolithic `rust-io` crate into three separate crates with clear responsibilities:
- `files-io`: File I/O operations (local + S3)
- `literature-io`: Literature acquisition functionality  
- `rust-io`: Python-facing facade that delegates to the above

---

## ✅ Strengths

### 1. Architecture & Design
- **Good use of Facade Pattern**: Clean separation of concerns
- **Single Responsibility Principle**: Each crate has a clear, focused purpose
- **Low Coupling**: Crates are properly decoupled through the facade

### 2. Code Quality
- ✅ Compiles successfully with `cargo check`
- ✅ Properly registers Python submodules in `sys.modules`
- ✅ Removes committed binary (`rust_io.so`), which is good practice
- ✅ Clean, readable code structure

### 3. Dependency Management
- ✅ Cargo.toml files updated correctly
- ✅ pyproject.toml updated to use `rust-io` instead of `files-io`
- ✅ Internal path dependencies properly configured

---

## ⚠️ Issues Found

### 🔴 [Blocking] API Breaking Changes

**Problem**: Three functions were removed from `rust_io.files` without replacement:
- `compute_sha256`
- `write_file`
- `validate_pdf_magic`

**Impact**: Any code directly importing and using these functions will fail at runtime. While `user_upload/service.py` has a Python fallback, other consumers may not.

**Recommendation**:
- Re-expose these functions either through `files-io` or the `rust-io` facade
- Consider adding deprecation warnings if planning a longer-term migration
- Maintain API compatibility unless explicitly planned and communicated

```rust
// Example: Add back these functions in files-io/py.rs or rust-io facade
#[pyfunction]
pub fn compute_sha256(file_path: &str) -> PyResult<String> {
    // implementation...
}
```

---

### 🟡 [Important] Python Version Requirement Change

**Problem**: `rust-io/pyproject.toml` changed from:
```toml
requires-python = ">=3.8"
```
to:
```toml
requires-python = ">=3.12"
```

**Impact**: This could break environments running Python 3.8-3.11.

**Recommendation**:
- Verify if Python 3.12+ is actually required
- Document this breaking change in PR/commits
- If possible, maintain compatibility with older versions

---

### 🟢 [Nit] Code Duplication

**Problem**: Submodule registration code is duplicated in `rust-io/src/lib.rs`:

```rust
m.py()
    .import("sys")?
    .getattr("modules")?
    .cast::<PyDict>()?
    .set_item("rust_io.literature", &literature)?;

// Same pattern repeated for "rust_io.files"
```

**Recommendation**: Extract to a helper function:

```rust
fn register_submodule(py: Python, parent: &Bound<PyModule>, name: &str, submodule: &Bound<PyModule>) -> PyResult<()> {
    parent.add_submodule(submodule)?;
    py.import("sys")?
        .getattr("modules")?
        .cast::<PyDict>()?
        .set_item(format!("{}.{}", parent.name()?, name), submodule)?;
    Ok(())
}
```

---

## 📊 Summary

| Aspect | Rating | Notes |
|--------|--------|-------|
| Architecture | 🟢 Excellent | Good separation of concerns |
| Code Quality | 🟢 Good | Compiles cleanly |
| API Compatibility | 🟡 Needs Attention | Breaking changes present |
| Dependencies | 🟢 Good | Properly configured |
| Documentation | ℹ️ Not Reviewed | - |

---

## 🎯 Decision

**🔄 Request Changes**

The blocking issue (API breaking changes) needs to be addressed before merging. The Python version change should also be confirmed and documented.

Once these issues are resolved, this refactor provides a clean, maintainable architecture that is ready to merge.

---

## 📝 Commit History Reviewed

- `c8bcb8f1 refactor(src): import from rust_io facade`
- `06170c5f chore(backend): switch dependency from files-io to rust-io`
- `23491257 fix(rust-io): register facade submodules for Python imports`
- `a44b33cb feat(rust-io): add pyproject.toml for Python package installation`
- `f04b0c52 refactor(rust-io): replace duplicate code with facade delegating to files-io and literature-io`
- `8e996c86 feat(literature-io): add all Rust source files`
- `80d09553 refactor(literature-io): convert to rlib-only, remove pymodule entry point`
- `1e22e101 refactor(files-io): convert to rlib-only, remove pymodule entry point`
