# Backend Security & Architecture Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix critical security vulnerabilities and architectural issues identified in the backend code review.

**Architecture:** Address path traversal, file upload limits, missing authentication, and API rate limiting. Fix chat reply synchronization, transaction safety, and type safety violations. All fixes follow TDD with isolated commits.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy async, pytest-asyncio, slowapi (rate limiting)

---

## Task 1: Add API key authentication to pipeline routes

**Files:**
- Modify: `backend/src/api/v1/pipeline.py:159` (start_pipeline_run signature)
- Modify: `backend/src/api/v1/pipeline.py:232` (get_pipeline_status signature)
- Create: `backend/tests/api/test_pipeline_auth.py`

**Step 1: Write the failing test**

```python
"""Tests for pipeline route authentication."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_pipeline_run_requires_api_key():
    """POST /api/v1/pipeline/run should require X-API-Key when API_KEY is configured."""
    with patch("src.core.config.get_config") as mock_cfg, \
         patch("src.utils.health.check_all_connections", new_callable=AsyncMock,
               return_value=AsyncMock(failed_services=AsyncMock(return_value=[]))):
        from src.core.config import Settings
        mock_cfg.return_value = Settings(api_key="test-secret")

        from app.main import create_app
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/pipeline/run",
                json={
                    "source_type": "online",
                    "mode": "full",
                    "query": "BRCA1",
                },
            )
            assert resp.status_code == 401


@pytest.mark.asyncio
async def test_pipeline_status_requires_api_key():
    """GET /api/v1/pipeline/runs/{id}/status should require X-API-Key."""
    with patch("src.core.config.get_config") as mock_cfg, \
         patch("src.utils.health.check_all_connections", new_callable=AsyncMock,
               return_value=AsyncMock(failed_services=AsyncMock(return_value=[]))):
        from src.core.config import Settings
        mock_cfg.return_value = Settings(api_key="test-secret")

        from app.main import create_app
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/pipeline/runs/test-run-id/status",
            )
            assert resp.status_code == 401
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/api/test_pipeline_auth.py -v`
Expected: FAIL — routes return 200/404 instead of 401.

**Step 3: Write minimal implementation**

Update `backend/src/api/v1/pipeline.py`:

```python
# Add import at top
from src.api.auth import require_api_key
from fastapi import Depends

# Update start_pipeline_run signature (line 159)
@router.post("/run", response_model=PipelineRunResponse, status_code=202)
async def start_pipeline_run(
    request: PipelineRunRequest,
    _api_key: str | None = Depends(require_api_key),
):
    ...

# Update get_pipeline_status signature (line 232)
@router.get("/runs/{processing_run_id}/status", response_model=PipelineStatusResponse)
async def get_pipeline_status(
    processing_run_id: str,
    _api_key: str | None = Depends(require_api_key),
):
    ...
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/api/test_pipeline_auth.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/api/v1/pipeline.py backend/tests/api/test_pipeline_auth.py
git commit -m "fix(backend): add API key authentication to pipeline routes

POST /pipeline/run and GET /pipeline/runs/{id}/status were missing
require_api_key dependency. All other write routes already had auth.
Now requires valid X-API-Key header when API_KEY env var is configured."
```

---

## Task 2: Add file size limit to pipeline upload

**Files:**
- Modify: `backend/src/api/v1/pipeline.py:182-189`
- Create: `backend/tests/api/test_pipeline_upload_limit.py`

**Step 1: Write the failing test**

```python
"""Tests for pipeline upload size limits."""
from __future__ import annotations

import base64
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_upload_rejects_oversized_files():
    """POST /api/v1/pipeline/run should reject files exceeding size limit."""
    # Create 101MB base64 payload (exceeds 100MB limit)
    large_content = base64.b64encode(b"x" * (101 * 1024 * 1024)).decode()

    with patch("src.core.config.get_config") as mock_cfg, \
         patch("src.utils.health.check_all_connections", new_callable=AsyncMock,
               return_value=AsyncMock(failed_services=AsyncMock(return_value=[]))):
        from src.core.config import Settings
        mock_cfg.return_value = Settings(
            api_key="test-secret",
            mineru_max_file_size_mb=100,
        )

        from app.main import create_app
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/pipeline/run",
                json={
                    "source_type": "local",
                    "mode": "full",
                    "content_base64": large_content,
                    "filename": "large.pdf",
                },
                headers={"X-API-Key": "test-secret"},
            )
            assert resp.status_code == 413
            assert "File too large" in resp.json()["detail"]
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/api/test_pipeline_upload_limit.py -v`
Expected: FAIL — no size validation, request proceeds to base64 decode.

**Step 3: Write minimal implementation**

Update `backend/src/api/v1/pipeline.py:182-189`:

```python
    # Decode base64 content and write to temp file if provided
    upload_file_path = None
    if request.content_base64:
        # Enforce file size limit
        max_size_bytes = get_config().mineru.max_file_size_mb * 1024 * 1024
        estimated_size = len(request.content_base64) * 3 // 4
        if estimated_size > max_size_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size: {get_config().mineru.max_file_size_mb}MB",
            )

        content_bytes = base64.b64decode(request.content_base64)
        fname = request.filename or f"{processing_run_id}.bin"
        temp_dir = Path("data/pipeline/uploads")
        temp_dir.mkdir(parents=True, exist_ok=True)
        upload_file_path = str(temp_dir / f"{processing_run_id}_{fname}")
        async with aiofiles.open(upload_file_path, "wb") as f:
            await f.write(content_bytes)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/api/test_pipeline_upload_limit.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/api/v1/pipeline.py backend/tests/api/test_pipeline_upload_limit.py
git commit -m "fix(backend): enforce file size limit on pipeline uploads

POST /pipeline/run accepted arbitrarily large base64 payloads, risking
disk exhaustion. Now validates estimated decoded size against
mineru_max_file_size_mb config before decoding. Returns 413 if exceeded."
```

---

## Task 3: Sanitize upload filename to prevent path traversal

**Files:**
- Modify: `backend/src/api/v1/pipeline.py:183-186`
- Create: `backend/tests/api/test_pipeline_path_traversal.py`

**Step 1: Write the failing test**

```python
"""Tests for pipeline upload path traversal prevention."""
from __future__ import annotations

import base64
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_upload_strips_directory_from_filename():
    """POST /api/v1/pipeline/run should strip directory components from filename."""
    small_content = base64.b64encode(b"test content").decode()

    with patch("src.core.config.get_config") as mock_cfg, \
         patch("src.utils.health.check_all_connections", new_callable=AsyncMock,
               return_value=AsyncMock(failed_services=AsyncMock(return_value=[]))), \
         patch("src.api.v1.pipeline.get_pipeline_runner") as mock_runner:

        from src.core.config import Settings
        mock_cfg.return_value = Settings(api_key="test-secret")

        # Mock runner to capture the state passed to start()
        captured_state = {}
        def capture_start(state):
            captured_state["upload_file_path"] = state.upload_file_path
            from unittest.mock import MagicMock
            return MagicMock(add_done_callback=lambda cb: None)

        mock_runner.return_value.start = capture_start

        from app.main import create_app
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/pipeline/run",
                json={
                    "source_type": "local",
                    "mode": "full",
                    "content_base64": small_content,
                    "filename": "../../etc/passwd",  # Path traversal attempt
                },
                headers={"X-API-Key": "test-secret"},
            )
            assert resp.status_code == 202

            # Verify directory components were stripped
            upload_path = captured_state["upload_file_path"]
            assert "../" not in upload_path
            assert "etc/passwd" not in upload_path
            assert upload_path.endswith("passwd")  # Only filename kept
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/api/test_pipeline_path_traversal.py -v`
Expected: FAIL — filename contains `../../etc/passwd`, path traversal succeeds.

**Step 3: Write minimal implementation**

Update `backend/src/api/v1/pipeline.py:183-186`:

```python
        content_bytes = base64.b64decode(request.content_base64)
        # Sanitize filename: strip directory components to prevent path traversal
        from pathlib import PurePosixPath
        raw_fname = request.filename or f"{processing_run_id}.bin"
        fname = PurePosixPath(raw_fname).name  # Keeps only the filename part
        temp_dir = Path("data/pipeline/uploads")
        temp_dir.mkdir(parents=True, exist_ok=True)
        upload_file_path = str(temp_dir / f"{processing_run_id}_{fname}")
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/api/test_pipeline_path_traversal.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/api/v1/pipeline.py backend/tests/api/test_pipeline_path_traversal.py
git commit -m "fix(backend): prevent path traversal in pipeline uploads

POST /pipeline/run accepted request.filename without sanitization,
allowing directory traversal (e.g. '../../etc/passwd'). Now uses
PurePosixPath.name to strip all directory components, keeping only
the filename part."
```

---

## Task 4: Add API rate limiting to write routes

**Files:**
- Add: `backend/pyproject.toml` (slowapi dependency)
- Create: `backend/src/api/rate_limit.py` (rate limiter singleton)
- Modify: `backend/app/main.py:95-100` (register middleware)
- Modify: `backend/src/api/v1/pipeline.py:159-195` (add rate limit, fix parameter names)
- Modify: `backend/src/api/v1/evidence.py:20` (add rate limit)
- Modify: `backend/src/api/v1/chat.py:35,73` (add rate limit to write routes)
- Create: `backend/tests/api/test_rate_limiting.py`

**Note:** evidence.py and chat.py write routes already have `Depends(require_api_key)`. This task only adds rate limiting.

**Step 1: Add slowapi to dependencies**

Update `backend/pyproject.toml`:

```toml
dependencies = [
    # ... existing dependencies ...
    "slowapi>=0.1.9",  # Rate limiting for FastAPI
]
```

Run: `cd backend && uv lock && uv sync`

**Step 2: Write the failing test**

```python
"""Tests for API rate limiting."""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_pipeline_run_rate_limited():
    """POST /api/v1/pipeline/run should be rate limited."""
    with patch("src.core.config.get_config") as mock_cfg, \
         patch("src.utils.health.check_all_connections", new_callable=AsyncMock,
               return_value=AsyncMock(failed_services=AsyncMock(return_value=[]))), \
         patch("src.api.v1.pipeline.get_pipeline_runner") as mock_runner:

        from src.core.config import Settings
        mock_cfg.return_value = Settings(api_key="test-secret")

        # Mock runner to avoid actual pipeline execution
        from unittest.mock import MagicMock
        mock_runner.return_value.start = MagicMock(
            return_value=MagicMock(add_done_callback=lambda cb: None)
        )

        from app.main import create_app
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Send 11 requests (limit is 10 per minute)
            responses = []
            for _ in range(11):
                resp = await client.post(
                    "/api/v1/pipeline/run",
                    json={
                        "source_type": "online",
                        "mode": "full",
                        "query": "BRCA1",
                    },
                    headers={"X-API-Key": "test-secret"},
                )
                responses.append(resp.status_code)

            # First 10 should succeed (202), 11th should be rate limited (429)
            assert responses[:10] == [202] * 10
            assert responses[10] == 429
```

**Step 3: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/api/test_rate_limiting.py -v`
Expected: FAIL — no rate limiting, all requests return 202.

**Step 4: Write minimal implementation**

Create `backend/src/api/rate_limit.py`:

```python
"""API rate limiting singleton."""
from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

# Global rate limiter (initialized here, registered in main.py)
limiter = Limiter(key_func=get_remote_address)
```

Update `backend/app/main.py:95-100` (after middleware registration):

```python
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from src.api.rate_limit import limiter

    # Register rate limiter
    _app.state.limiter = limiter
    _app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

Update `backend/src/api/v1/pipeline.py:159-195`:

```python
from src.api.rate_limit import limiter
from starlette.requests import Request

# ... other imports ...

@router.post("/run", response_model=PipelineRunResponse, status_code=202)
@limiter.limit("10/minute")
async def start_pipeline_run(
    request: Request,  # Required by slowapi - must be first parameter
    body: PipelineRunRequest,  # Renamed from 'request' to avoid conflict
    _api_key: str | None = Depends(require_api_key),
):
    """Start a new pipeline run.

    Returns immediately with processing_run_id. Poll status_url for progress.
    N3 fix: Checks for duplicate in-progress runs before starting.
    """
    runner = get_pipeline_runner()

    # N3: Duplicate run prevention — check if same source is already being processed
    source_key = body.filename or (body.query or "")
    if source_key and runner.is_running_for_source(source_key):
        raise HTTPException(
            status_code=409,
            detail=f"A pipeline run is already in progress for this source: {source_key}",
        )

    processing_run_id = str(uuid.uuid4())
    source_document_id = str(uuid.uuid4())

    # Decode base64 content and write to temp file if provided
    upload_file_path = None
    if body.content_base64:
        content_bytes = base64.b64decode(body.content_base64)
        fname = body.filename or f"{processing_run_id}.bin"
        temp_dir = Path("data/pipeline/uploads")
        temp_dir.mkdir(parents=True, exist_ok=True)
        upload_file_path = str(temp_dir / f"{processing_run_id}_{fname}")
        async with aiofiles.open(upload_file_path, "wb") as f:
            await f.write(content_bytes)

    # Determine online acquisition action
    online_action = None
    if body.source_type == "online":
        if body.identifiers:
            online_action = "fetch"
        else:
            online_action = "search"

    initial_state = PipelineGraphState(
        processing_run_id=processing_run_id,
        source_document_id=source_document_id,
        mode=PipelineMode(body.mode),
        source_type=SourceType(body.source_type),
        target_phase=body.target_phase,
        source_key=source_key or None,
        upload_file_path=upload_file_path,
        query=body.query,
        identifiers=body.identifiers,
        action=online_action,
        created_at=datetime.now().isoformat(),
    )

    task = runner.start(initial_state)

    # Clean up temp file after pipeline completes (success or failure)
    if upload_file_path:
        def _cleanup_temp_file(t: object) -> None:
            try:
                Path(upload_file_path).unlink(missing_ok=True)
            except OSError:
                pass

        task.add_done_callback(_cleanup_temp_file)

    return PipelineRunResponse(
        processing_run_id=processing_run_id,
        source_document_id=source_document_id,
        status="accepted",
        status_url=f"/api/v1/pipeline/runs/{processing_run_id}/status",
    )
```

Update `backend/src/api/v1/evidence.py:20`:

```python
from src.api.rate_limit import limiter
from starlette.requests import Request

@router.patch("/{canonical_evidence_id}", response_model=PatchResultResponse)
@limiter.limit("30/minute")
async def patch_evidence(
    request: Request,  # Required by slowapi
    canonical_evidence_id: UUID,
    patch: EvidencePatchRequest,
    session: AsyncSession = Depends(get_db_session),
    _api_key: str | None = Depends(require_api_key),
) -> PatchResultResponse:
    ...
```

Update `backend/src/api/v1/chat.py:35,73`:

```python
from src.api.rate_limit import limiter
from starlette.requests import Request

@router.post("/sessions", response_model=ChatSessionResponse)
@limiter.limit("30/minute")
async def create_session(
    request: Request,  # Required by slowapi
    req: CreateSessionRequest,
    session: AsyncSession = Depends(get_db_session),
    _api_key: str | None = Depends(require_api_key),
) -> ChatSessionResponse:
    ...

@router.post("/sessions/{session_id}/messages", response_model=ChatMessageResponse)
@limiter.limit("60/minute")
async def append_message(
    request: Request,  # Required by slowapi
    session_id: UUID,
    req: AppendMessageRequest,
    session: AsyncSession = Depends(get_db_session),
    _api_key: str | None = Depends(require_api_key),
) -> ChatMessageResponse:
    ...
```

**Step 5: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/api/test_rate_limiting.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/src/api/rate_limit.py backend/app/main.py backend/src/api/v1/pipeline.py backend/src/api/v1/evidence.py backend/src/api/v1/chat.py backend/tests/api/test_rate_limiting.py
git commit -m "feat(backend): add API rate limiting to write routes

POST /pipeline/run: 10/minute (CPU/GPU intensive)
PATCH /evidence: 30/minute
POST /chat/sessions, /messages: 30-60/minute

Prevents abuse and resource exhaustion. Uses slowapi with per-IP
tracking. Returns 429 Too Many Requests when limit exceeded.

Note: slowapi requires request: Request as first parameter, so
Pydantic body parameters were renamed (request -> body) where needed."
```

---

## Task 5: Remove duplicate docstring in config.py

**Files:**
- Modify: `backend/src/core/config.py:3-21`

**Step 1: Fix the duplicate**

Update `backend/src/core/config.py:1-22`:

```python
"""Configuration management middleware.

All settings are loaded from ``.env.local`` / ``.env`` / environment variables
via pydantic-settings. Preferred env prefixes are ``FAST_LLM_*`` and
``REASONING_LLM_*``. Legacy ``LLM_*`` / ``REASONING_LLM_*`` variables remain
supported as fallbacks. Nested domain models are constructed from the resolved
flat fields by a ``model_validator``.

    from src.core.config import get_config

    cfg = get_config()              # singleton
    cfg.llm.api_key                 # preferred: nested access
    cfg.postgresql.host             # nested domain
    cfg.llm_api_key                 # also available as flat field
"""

from __future__ import annotations
```

**Step 2: Commit**

```bash
git add backend/src/core/config.py
git commit -m "chore(backend): remove duplicate docstring in config.py"
```

---

## Task 6: Type error_response with TypedDict

**Files:**
- Modify: `backend/app/main.py:26-37`
- Create: `backend/tests/api/test_error_response_type.py`

**Step 1: Write the failing test**

```python
"""Tests for error response type safety."""
from __future__ import annotations

import ast
import inspect


def test_error_response_uses_typed_dict():
    """_error_response should use TypedDict for body and error fields."""
    from app.main import _error_response

    # Get function source and parse AST
    source = inspect.getsource(_error_response)
    tree = ast.parse(source)

    # Find the function definition
    func_def = tree.body[0]
    assert isinstance(func_def, ast.FunctionDef)

    # Check that function body uses TypedDict types
    found_error_detail_typed = False
    found_body_typed = False

    for node in ast.walk(func_def):
        if isinstance(node, ast.AnnAssign):
            # Check for: error_detail: ErrorDetail = ...
            if isinstance(node.target, ast.Name):
                if node.target.id == "error_detail" and isinstance(node.annotation, ast.Name):
                    if node.annotation.id == "ErrorDetail":
                        found_error_detail_typed = True
                # Check for: body: ErrorResponseBody = ...
                if node.target.id == "body" and isinstance(node.annotation, ast.Name):
                    if node.annotation.id == "ErrorResponseBody":
                        found_body_typed = True

    assert found_error_detail_typed, "error_detail should be typed as ErrorDetail"
    assert found_body_typed, "body should be typed as ErrorResponseBody"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/api/test_error_response_type.py -v`
Expected: FAIL — current code uses `dict[str, Any]` instead of TypedDict.

**Step 3: Write minimal implementation**

Update `backend/app/main.py:26-37`:

```python
from typing import TypedDict


class ErrorDetail(TypedDict, total=False):
    """Error detail structure."""
    code: str
    message: str
    details: list[dict[str, Any]]


class ErrorResponseBody(TypedDict):
    """Error response envelope."""
    error: ErrorDetail
    request_id: str


def _error_response(
    *,
    code: str,
    message: str,
    request_id: str,
    status: int,
    errors: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    """Build a structured error response envelope with X-Request-ID header."""
    error_detail: ErrorDetail = {
        "code": code,
        "message": message,
    }
    if errors is not None:
        error_detail["details"] = errors

    body: ErrorResponseBody = {
        "error": error_detail,
        "request_id": request_id,
    }
    return JSONResponse(status_code=status, content=body, headers={"X-Request-ID": request_id})
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/api/test_error_response_type.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/main.py backend/tests/api/test_error_response_type.py
git commit -m "fix(backend): type error_response with TypedDict

_error_response used bare dict[str, Any] for body and error fields,
violating project rule 22 (no bare dict return types). Now uses
ErrorResponseBody and ErrorDetail TypedDicts for type safety."
```

---

## Execution Notes

### Task Dependency Order

```
Task 1 (pipeline auth)      — independent
Task 2 (file size limit)   — independent
Task 3 (path traversal)    — independent
Task 4 (rate limiting)     — independent (but touches multiple files)
Task 5 (docstring)         — independent (trivial)
Task 6 (error type)        — independent
```

### Workflow Steps Per Task

Each task must follow this workflow:
1. Write the failing test → verify it fails
2. Write the minimal implementation → verify it passes
3. Run the full test suite: `cd backend && uv run pytest tests/api/ -x -q`
4. Commit using conventional commits format

### Post-Execution Steps

After all tasks are complete:
1. Run full lint: `cd backend && uv run ruff check app src`
2. Run full test suite: `cd backend && uv run pytest tests/ -q`
3. Update `progress.txt` with security fixes completion

### Estimated Effort

~1.5 hours total. Tasks 1-3 are straightforward (10 min each). Task 4 is more complex (30 min). Tasks 5-6 are quick (5 min each).

### Security Impact

- **Task 1**: Closes authentication gap on CPU/GPU-intensive pipeline routes
- **Task 2**: Prevents disk exhaustion from oversized uploads
- **Task 3**: Prevents path traversal attacks on file system
- **Task 4**: Mitigates abuse and DoS attacks on write endpoints

### Medium Issues Not Addressed

The following Medium issues from the review are deferred to a separate plan:
- M1: Chat sync reply blocking (requires architectural decision: background task vs client-side streaming)
- M2: TRUNCATE transaction safety (requires database-specific testing)
- M3: FK migration validation (requires running database)
- M4: Error state persistence (requires integration testing with database failure)
- M5: Provider startup timing (requires config validation framework)
- M6: Chinese pattern readability (code style, not security)
