## 2026-03-12 Issues
- Tooling in this execution environment may lack runtime deps (e.g., fastapi) and linters (ruff), which can block verification commands; track and resolve when encountered.

## 2026-03-13 Task 3.1: Committed secret forward-fix (partial)
- Found hard-coded Qdrant API key in tracked `tests/docker-compose.yml`.
- Forward-fix applied: replaced literal value with compose env-var substitution `QDRANT_API_KEY=${QDRANT_API_KEY}`.
- Verification: `uv run pytest -q` still passes.
- **Action required**: rotate the compromised credential out-of-band; additional files still contain leaked literals and must be scrubbed.


## 2026-03-12 23:17 Task 0.1: Resolved & Observed Issues

### Resolved
- **Missing dev tools**: ruff, black, mypy were not installed in venv despite being declared in pyproject.toml `[project.optional-dependencies]`
  - **Fix**: `uv pip install ruff black mypy` (installed in <1 min)
  - **Root cause**: `uv sync` alone does not install optional dependencies; need explicit install or `uv sync --extra dev`

### Observed (not blocking Task 0.1)
- **Python version mismatch**: pyproject.toml targets py312, venv runs py3.11.14
  - **Impact**: Black warns about AST parsing safety; not critical for development
  - **Defer**: Address in environment setup task if needed

- **Missing type stubs**: yaml, requests, celery, kombu lack py.typed markers
  - **Impact**: Mypy reports import-untyped errors
  - **Defer**: Install type stubs in dedicated type-safety task

- **Pytest collection errors**: 9 errors out of 502 items
  - **Impact**: Some tests may not run
  - **Defer**: Investigate in test organization task

