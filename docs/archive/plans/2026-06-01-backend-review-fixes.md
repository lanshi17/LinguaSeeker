# Backend Review Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix all critical and major issues found in the backend & database review — session commit bug, missing auth, SSE middleware conflict, state persistence race condition, unbounded cache, httpx client lifecycle, VLM unload, type safety violations, model-server dependency declarations, and missing API route tests.

**Architecture:** Each task is an isolated, independently committable change. The session commit fix in `deps.py` is highest priority (data loss). Auth is added as an `X-API-Key` header dependency. The httpx client reuse requires injecting the provider through `Phase4ServiceFactory` so it lives for the application lifetime. Each task follows TDD.

**Tech Stack:** FastAPI, SQLAlchemy async, PostgreSQL, pytest-asyncio, httpx, Pydantic

---

### Task 1: Fix session commit bug — `get_db_session` never commits

**Files:**
- Modify: `backend/src/api/deps.py:27-31`
- Create: `backend/tests/api/test_deps_session.py`

**Step 1: Write the failing test**

```python
"""Tests for get_db_session commit/rollback behavior."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_get_db_session_commits_on_success():
    """get_db_session commits the session when the route handler succeeds.

    Uses a real FastAPI route to exercise the full yield-dependency lifecycle,
    because aclose() on an async generator does NOT execute code after yield
    the same way FastAPI's dependency injection does.
    """
    from fastapi import Depends, FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.api.deps import get_db_session

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    test_app = FastAPI()

    @test_app.post("/test-write")
    async def test_write(session: AsyncSession = Depends(get_db_session)):
        # Simulate a write operation (service calls flush internally)
        session.add(MagicMock())
        return {"ok": True}

    with patch("src.api.deps.get_session_factory", return_value=mock_factory):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/test-write")
            assert resp.status_code == 200

    mock_session.commit.assert_awaited_once()
    mock_session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_db_session_rollbacks_on_exception():
    """get_db_session rolls back when the route handler raises."""
    from fastapi import Depends, FastAPI, HTTPException
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.api.deps import get_db_session

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    test_app = FastAPI()

    @test_app.post("/test-fail")
    async def test_fail(session: AsyncSession = Depends(get_db_session)):
        raise HTTPException(status_code=500, detail="boom")

    @test_app.exception_handler(500)
    async def handler(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"error": str(exc.detail)})

    with patch("src.api.deps.get_session_factory", return_value=mock_factory):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/test-fail")
            assert resp.status_code == 500

    mock_session.rollback.assert_awaited_once()
    mock_session.commit.assert_not_awaited()
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/api/test_deps_session.py -v`
Expected: FAIL — `commit` not called because `get_db_session` just yields without committing.

**Step 3: Write minimal implementation**

Replace `backend/src/api/deps.py:27-31`:

```python
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency: yield an async database session.

    Commits on successful handler exit; rolls back on exception.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/api/test_deps_session.py -v`
Expected: PASS

**Step 5: Run existing tests to ensure no regressions**

Run: `cd backend && uv run pytest tests/ -x -q`
Expected: All existing tests still pass.

**Step 6: Commit**

```bash
git add backend/src/api/deps.py backend/tests/api/test_deps_session.py
git commit -m "fix(backend): commit session on successful exit, rollback on exception

get_db_session previously yielded a session without committing. When the
context manager exited, the session closed and all uncommitted changes
were silently rolled back — every write route (PATCH /evidence, POST
/chat/sessions, POST /chat/messages) lost its data.

Now commits on successful handler exit and rolls back on exception."
```

---

### Task 2: Add API key authentication to write routes

**Files:**
- Create: `backend/src/api/auth.py`
- Modify: `backend/src/core/config.py` — add `api_key: str = ""` to Settings
- Modify: `backend/src/api/v1/evidence.py` — inject auth dependency
- Modify: `backend/src/api/v1/chat.py` — inject auth dependency
- Modify: `backend/app/main.py` — pass `reviewer_id` from auth context
- Create: `backend/tests/api/test_auth.py`

**Step 1: Write the failing test**

```python
"""Tests for API key authentication."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def _mock_config_with_api_key():
    """Provide config with API_KEY set."""
    with patch("src.core.config.get_config") as mock_cfg:
        from src.core.config import Settings
        mock_cfg.return_value = Settings(api_key="test-secret-key")
        yield mock_cfg


@pytest.mark.asyncio
async def test_write_route_rejected_without_api_key(_mock_config_with_api_key):
    """Write routes should return 401 when API_KEY is set but not provided."""
    with (
        patch("src.utils.health.check_all_connections", new_callable=AsyncMock,
              return_value=MagicMock(failed_services=MagicMock(return_value=[]))),
    ):
        from app.main import create_app
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.patch(
                "/api/v1/evidence/00000000-0000-0000-0000-000000000000",
                json={"fields": {"gene": "BRCA1"}},
            )
            assert resp.status_code == 401


@pytest.mark.asyncio
async def test_write_route_accepted_with_valid_api_key(_mock_config_with_api_key):
    """Write routes should accept requests with valid X-API-Key header."""
    from sqlalchemy.ext.asyncio import AsyncSession

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.commit = AsyncMock()

    with (
        patch("src.utils.health.check_all_connections", new_callable=AsyncMock,
              return_value=MagicMock(failed_services=MagicMock(return_value=[]))),
        # Patch in the route module where get_phase4_factory is bound (not deps)
        patch("src.api.v1.evidence.get_phase4_factory") as mock_factory,
        # Mock get_db_session to avoid real PostgreSQL connection
        patch("src.api.deps.get_session_factory") as mock_sf,
    ):
        mock_sf.return_value = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_session),
                __aexit__=AsyncMock(return_value=False),
            )
        )

        from src.core.visualize_evidence_with_expert_in_loop.feedback_service import PatchResult
        from src.core.visualize_evidence_with_expert_in_loop.contracts import ReviewStatus

        mock_service = MagicMock()
        mock_service.patch_evidence = AsyncMock(return_value=PatchResult(
            canonical_evidence_id="00000000-0000-0000-0000-000000000000",
            old_status=ReviewStatus.PROVISIONAL,
            new_status=ReviewStatus.CORRECTED,
            deltas=1,
            field_deltas=[],
        ))
        mock_factory.return_value.create_feedback_service.return_value = mock_service

        from app.main import create_app
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.patch(
                "/api/v1/evidence/00000000-0000-0000-0000-000000000000",
                json={"fields": {"gene": "BRCA1"}},
                headers={"X-API-Key": "test-secret-key"},
            )
            assert resp.status_code == 200


@pytest.mark.asyncio
async def test_read_routes_open_when_no_api_key_configured():
    """When API_KEY is empty, all routes are accessible without auth."""
    with (
        patch("src.core.config.get_config") as mock_cfg,
        patch("src.utils.health.check_all_connections", new_callable=AsyncMock,
              return_value=MagicMock(failed_services=MagicMock(return_value=[]))),
    ):
        from src.core.config import Settings
        mock_cfg.return_value = Settings(api_key="")  # No key configured

        from app.main import create_app
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")
            assert resp.status_code == 200
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/api/test_auth.py -v`
Expected: FAIL — no auth dependency exists.

**Step 3: Write minimal implementation**

Create `backend/src/api/auth.py`:

```python
"""API key authentication dependency."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

from src.core.config import get_config

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(
    api_key: str | None = Security(_api_key_header),
) -> str | None:
    """Validate X-API-Key header against configured API_KEY.

    Returns the validated key string, or None if no key is configured
    (auth disabled). Routes that need a reviewer_id can use this value.
    """
    cfg = get_config()
    if not cfg.api_key:
        return None  # Auth disabled — no key configured

    if api_key is None:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")

    if api_key != cfg.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return api_key
```

Add to `Settings` in `backend/src/core/config.py` (after `debug: bool = False`):

```python
    api_key: str = ""  # X-API-Key for write route auth; empty = disabled
```

Update `backend/src/api/v1/evidence.py`:

```python
from src.api.auth import require_api_key

@router.patch("/{canonical_evidence_id}", response_model=PatchResultResponse)
async def patch_evidence(
    canonical_evidence_id: UUID,
    patch: EvidencePatchRequest,
    session: AsyncSession = Depends(get_db_session),
    _api_key: str | None = Depends(require_api_key),
) -> PatchResultResponse:
    ...
```

Apply the same `Depends(require_api_key)` to write routes in `chat.py` (`create_session`, `append_message`, `stream_reply`).

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/api/test_auth.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/api/auth.py backend/src/core/config.py backend/src/api/v1/evidence.py backend/src/api/v1/chat.py backend/tests/api/test_auth.py
git commit -m "feat(backend): add X-API-Key authentication to write routes

All mutation routes (PATCH /evidence, POST /chat/*) now require a valid
X-API-Key header when API_KEY env var is configured. Read-only routes
and health check remain public. When API_KEY is empty, auth is disabled
(for development)."
```

---

### Task 3: Fix state persistence race condition — use PostgreSQL upsert

**Files:**
- Modify: `backend/src/agents/state_persistence.py:62-77`
- Test: `backend/tests/agents/test_state_persistence_layer.py`

**Step 1: Write the failing test**

Add to existing `backend/tests/agents/test_state_persistence_layer.py`:

```python
@pytest.mark.asyncio
async def test_session_bound_save_uses_upsert():
    """SessionBoundStatePersistence.save() should use INSERT ON CONFLICT
    rather than SELECT then conditional INSERT/UPDATE to avoid race conditions."""
    from unittest.mock import AsyncMock, MagicMock
    from src.agents.state_persistence import SessionBoundStatePersistence
    from src.agents.contracts import PipelineGraphState, PipelineMode, SourceType, PipelineStatus

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()

    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    persistence = SessionBoundStatePersistence(mock_factory)

    state = PipelineGraphState(
        processing_run_id="run-upsert-test",
        source_document_id="doc-1",
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
        pipeline_status=PipelineStatus.RUNNING,
    )

    await persistence.save(state)

    # Verify execute was called (INSERT ... ON CONFLICT) rather than
    # session.get + session.add pattern
    mock_session.execute.assert_awaited()
    mock_session.get.assert_not_awaited()
    mock_session.add.assert_not_called()
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/agents/test_state_persistence_layer.py -v`
Expected: FAIL — current code uses `session.get()` then `session.add()`.

**Step 3: Write minimal implementation**

Add import at top of `backend/src/agents/state_persistence.py`:
```python
from sqlalchemy.dialects.postgresql import insert as pg_insert
```

Replace `SessionBoundStatePersistence.save()`:

```python
    async def save(self, state: PipelineGraphState) -> None:
        async with self._session_factory() as session:
            state_json = state.model_dump(mode="json")
            stmt = (
                pg_insert(PipelineRunState)
                .values(
                    processing_run_id=UUID(state.processing_run_id),
                    source_document_id=UUID(state.source_document_id),
                    state_json=state_json,
                )
                .on_conflict_do_update(
                    index_elements=["processing_run_id"],
                    set_={"state_json": state_json},
                )
            )
            await session.execute(stmt)
            await session.commit()
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/agents/test_state_persistence_layer.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/agents/state_persistence.py backend/tests/agents/test_state_persistence_layer.py
git commit -m "fix(backend): use PostgreSQL upsert in SessionBoundStatePersistence

The previous SELECT-then-INSERT/UPDATE pattern had a race condition:
concurrent saves for the same processing_run_id could both see no
existing row and both try to insert, causing a unique constraint
violation. Now uses INSERT ... ON CONFLICT DO UPDATE."
```

---

### Task 4: Add LRU eviction to PipelineRunner._last_states

**Files:**
- Modify: `backend/src/agents/runner.py`
- Test: `backend/tests/agents/test_runner.py`

**Step 1: Write the failing test**

Add to existing `backend/tests/agents/test_runner.py`:

```python
def test_runner_evicts_oldest_states_beyond_limit():
    """Runner should evict oldest cached states when exceeding max size.

    Tests through _remember_state() helper which is called by start(),
    not by directly manipulating _last_states (which bypasses eviction).
    """
    from src.agents.runner import PipelineRunner
    from src.agents.contracts import PipelineGraphState, PipelineMode, SourceType, PipelineStatus
    from unittest.mock import MagicMock, AsyncMock

    runner = PipelineRunner(
        orchestrator=MagicMock(),
        semaphore=MagicMock(),
        state_persistence=MagicMock(),
    )

    # Use _remember_state helper to go through eviction path
    for i in range(105):
        state = PipelineGraphState(
            processing_run_id=f"run-{i}",
            source_document_id=f"doc-{i}",
            mode=PipelineMode.FULL,
            source_type=SourceType.LOCAL,
            pipeline_status=PipelineStatus.COMPLETED,
        )
        runner._remember_state(f"run-{i}", state)

    assert len(runner._last_states) <= 100
    assert "run-104" in runner._last_states  # newest kept
    assert "run-0" not in runner._last_states  # oldest evicted
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/agents/test_runner.py::test_runner_evicts_oldest_states_beyond_limit -v`
Expected: FAIL — `_remember_state` doesn't exist, and `_last_states` is a plain dict.

**Step 3: Write minimal implementation**

Replace `_last_states` type and add helper in `backend/src/agents/runner.py`:

```python
from collections import OrderedDict

class PipelineRunner:
    """Manages background execution of pipeline runs."""

    _MAX_CACHED_STATES = 100

    def __init__(self, orchestrator, semaphore, state_persistence):
        self._orchestrator = orchestrator
        self._semaphore = semaphore
        self._persistence = state_persistence
        self._active_tasks: dict[str, asyncio.Task] = {}
        self._last_states: OrderedDict[str, PipelineGraphState] = OrderedDict()

    def _remember_state(self, run_id: str, state: PipelineGraphState) -> None:
        """Store a state in the cache, evicting the oldest if over limit."""
        self._last_states[run_id] = state
        self._last_states.move_to_end(run_id)
        while len(self._last_states) > self._MAX_CACHED_STATES:
            self._last_states.popitem(last=False)
```

Update all `self._last_states[run_id] = ...` assignments in `_run_pipeline` and `start` to use `self._remember_state(run_id, ...)` instead.

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/agents/test_runner.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/agents/runner.py backend/tests/agents/test_runner.py
git commit -m "fix(backend): add LRU eviction to PipelineRunner._last_states

Previously _last_states grew unbounded, accumulating every completed
run's state indefinitely. Now uses OrderedDict with a 100-entry cap
via _remember_state() helper, evicting the oldest entries."
```

---

### Task 5: Reuse httpx.AsyncClient in ReasoningLLMProvider via factory injection

**Files:**
- Modify: `backend/src/core/visualize_evidence_with_expert_in_loop/providers.py`
- Modify: `backend/src/agents/phase_4_factory.py` — hold singleton provider
- Modify: `backend/src/core/visualize_evidence_with_expert_in_loop/chat_service.py` — accept provider via constructor
- Modify: `backend/app/main.py` — close provider on shutdown
- Test: `backend/tests/phase4/test_providers.py`

**Step 1: Write the failing test**

Add to `backend/tests/phase4/test_providers.py`:

```python
@pytest.mark.asyncio
async def test_reasoning_llm_provider_reuses_httpx_client():
    """ReasoningLLMProvider should reuse a single httpx.AsyncClient across calls."""
    from unittest.mock import AsyncMock, MagicMock, patch

    with patch("src.core.visualize_evidence_with_expert_in_loop.providers.get_config") as mock_cfg:
        mock_cfg.return_value.reasoning = MagicMock(
            api_key="test-key",
            model="test-model",
            base_url="http://localhost:8001",
            timeout=30,
        )
        from src.core.visualize_evidence_with_expert_in_loop.providers import ReasoningLLMProvider

        provider = ReasoningLLMProvider()

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "test"}}]}
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        with patch("httpx.AsyncClient", return_value=mock_client):
            await provider.generate(system_prompt="test", user_message="test")
            await provider.generate(system_prompt="test", user_message="test")

            # httpx.AsyncClient should only be instantiated once
            import httpx
            assert httpx.AsyncClient.call_count == 1

        await provider.close()


@pytest.mark.asyncio
async def test_chat_service_uses_injected_provider():
    """ChatService should use an injected provider, not create a new one per call."""
    from unittest.mock import AsyncMock, MagicMock, patch
    from src.core.visualize_evidence_with_expert_in_loop.chat_service import ChatService

    mock_session = AsyncMock()
    mock_provider = MagicMock()
    mock_provider.generate = AsyncMock(return_value="test reply")

    service = ChatService(session=mock_session, reasoning_provider=mock_provider)

    with patch.object(service, "_build_evidence_context", new_callable=AsyncMock, return_value="ctx"):
        await service.generate_reply(
            session_id=MagicMock(),
            user_message="What is BRCA1?",
            evidence_id=MagicMock(),
        )

    mock_provider.generate.assert_awaited_once()
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/phase4/test_providers.py -v`
Expected: FAIL — `ChatService` creates `ReasoningLLMProvider()` inside `generate_reply`.

**Step 3: Write minimal implementation**

Refactor `ReasoningLLMProvider` in `providers.py` to lazily create and cache the client:

```python
class ReasoningLLMProvider:
    def __init__(self) -> None:
        cfg = get_config()
        self._api_key = cfg.reasoning.api_key
        self._model = cfg.reasoning.model
        self._base_url = cfg.reasoning.base_url
        self._timeout = cfg.reasoning.timeout
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    # generate() and stream() use self._get_client() instead of creating new clients
```

Update `Phase4ServiceFactory` to hold a singleton provider:

```python
class Phase4ServiceFactory:
    def __init__(self, cfg: Settings):
        self._cfg = cfg
        self._delta_audit = DeltaAuditService()
        self._reasoning_provider = ReasoningLLMProvider()

    @property
    def reasoning_provider(self) -> ReasoningLLMProvider:
        return self._reasoning_provider

    def create_chat_service(self, session: AsyncSession) -> ChatService:
        return ChatService(session=session, reasoning_provider=self._reasoning_provider)

    async def close(self) -> None:
        await self._reasoning_provider.close()
```

Update `ChatService.__init__` to accept the provider:

```python
class ChatService:
    def __init__(self, session: AsyncSession, reasoning_provider: ReasoningLLMProvider | None = None):
        self._session = session
        self._reasoning_provider = reasoning_provider
```

Remove the `from ...providers import ReasoningLLMProvider` inside `generate_reply` and `stream_reply` — use `self._reasoning_provider` instead.

In `backend/app/main.py` lifespan teardown, close the factory:

```python
yield
phase4_factory = get_phase4_factory()
await phase4_factory.close()
await dispose_engine()
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/phase4/test_providers.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/visualize_evidence_with_expert_in_loop/providers.py backend/src/agents/phase_4_factory.py backend/src/core/visualize_evidence_with_expert_in_loop/chat_service.py backend/app/main.py backend/tests/phase4/test_providers.py
git commit -m "fix(backend): reuse httpx.AsyncClient via Phase4ServiceFactory injection

Previously ChatService created a new ReasoningLLMProvider (and thus a
new httpx.AsyncClient connection pool) on every request. Now the provider
is a singleton on Phase4ServiceFactory, injected into ChatService at
construction time, and closed during app lifespan teardown."
```

---

### Task 6: Remove per-request VLM model unload

**Files:**
- Modify: `backend/services/model-server/app/api/vlm.py:108-117`
- Modify: `backend/services/model-server/tests/test_vlm_api.py:61-62` — update existing test
- Create: `backend/services/model-server/tests/test_vlm_no_unload.py`

**Step 1: Write the failing test**

Create `backend/services/model-server/tests/test_vlm_no_unload.py`:

```python
"""Tests verifying VLM model stays loaded after inference."""
from unittest.mock import MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _make_client_with_mock_vlm():
    """Create test client with a mock VLM service."""
    with patch("app.domain.vlm.vllm.LLM"), \
         patch("app.domain.vlm.MinerUClient"):
        from app.domain.vlm import VLMService
        from app.api import vlm

        svc = VLMService(model_id="test-model")
        svc._ready = True
        svc._client = MagicMock()
        svc._client.two_step_extract.return_value = (
            "# Test\n\nContent",
            [{"page_number": 1, "markdown": "# Test", "figures": [], "tables": []}],
        )
        vlm.bind(svc)
        app = FastAPI()
        app.include_router(vlm.router)
        return TestClient(app), svc


def _make_test_image_b64() -> str:
    import base64, io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color="white").save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def test_vlm_model_stays_loaded_after_inference():
    """VLM model should NOT be unloaded after each inference request.

    Unloading forces a full model reload on the next request, adding
    minutes of latency per page for multi-page documents.
    """
    client, svc = _make_client_with_mock_vlm()
    img_b64 = _make_test_image_b64()

    resp = client.post("/v1/chat/completions", json={
        "model": "test-model",
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": "Extract."},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
        ]}],
    })

    assert resp.status_code == 200
    # Model should still be loaded (ready=True, client not None)
    assert svc.ready is True
    assert svc._client is not None
```

**Step 2: Run test to verify it fails**

Run: `cd backend/services/model-server && uv run pytest tests/test_vlm_no_unload.py -v`
Expected: FAIL — current code calls `_service.unload()` in `finally`.

**Step 3: Write minimal implementation**

In `backend/services/model-server/app/api/vlm.py`, remove the `finally` block (lines 116-117):

```python
    try:
        result = _service.infer(image=images[0])
    except VLMInferenceError as exc:
        logger.error("VLM inference failed (upstream): {exc}", exc=exc)
        raise HTTPException(status_code=502, detail=f"VLM upstream failure: {exc}") from exc
    except Exception as exc:
        logger.error("VLM inference failed: {exc}", exc=exc)
        raise HTTPException(status_code=500, detail=f"VLM inference failed: {exc}") from exc
    # Model stays loaded — unload() was removed intentionally.
```

Update the existing test in `backend/services/model-server/tests/test_vlm_api.py` — change lines 61-62 from:

```python
    assert svc._client is None
    assert svc.ready is False
```

to:

```python
    assert svc._client is not None
    assert svc.ready is True
```

**Step 3b: Add graceful VLM shutdown to model-server lifespan**

The model-server's lifespan shutdown (in `backend/services/model-server/main.py`) should call `_service.unload()` to free GPU memory on process exit. Find the shutdown hook and add:

```python
# In lifespan shutdown:
if _service is not None:
    _service.unload()
```

This ensures GPU memory is freed at shutdown without the per-request penalty.

**Step 4: Run test to verify it passes**

Run: `cd backend/services/model-server && uv run pytest tests/ -v`
Expected: PASS (both new and updated existing tests)

**Step: Commit**

```bash
git add backend/services/model-server/app/api/vlm.py backend/services/model-server/tests/test_vlm_api.py backend/services/model-server/tests/test_vlm_no_unload.py
git commit -m "fix(model-server): remove per-request VLM model unload

The VLM route called _service.unload() in a finally block after every
inference, destroying the vllm engine and forcing a full model reload
on the next request. For multi-page documents processed sequentially,
this added minutes of latency per page. Embedding and rerank routes
don't unload — VLM was the only outlier."
```

---

### Task 7: Convert RequestMonitorMiddleware from BaseHTTPMiddleware to raw ASGI

**Files:**
- Modify: `backend/src/utils/middleware.py`
- Test: `backend/tests/utils/test_middleware.py`

**Step 1: Write the failing test**

Add to `backend/tests/utils/test_middleware.py`:

```python
@pytest.mark.asyncio
async def test_sse_streaming_not_broken_by_middleware():
    """SSE streaming endpoint should work correctly through the middleware.

    BaseHTTPMiddleware buffers the full response body, breaking SSE/chunked
    streaming. The middleware must be raw ASGI to pass through streaming.
    """
    from fastapi import FastAPI
    from fastapi.responses import StreamingResponse
    from httpx import ASGITransport, AsyncClient
    from src.utils.middleware import add_request_monitoring

    app = FastAPI()
    add_request_monitoring(app)

    @app.get("/stream")
    async def stream():
        async def generate():
            yield "data: chunk1\n\n"
            yield "data: chunk2\n\n"
        return StreamingResponse(generate(), media_type="text/event-stream")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        chunks = []
        async with client.stream("GET", "/stream") as resp:
            assert resp.status_code == 200
            async for line in resp.aiter_lines():
                if line.strip():
                    chunks.append(line)

    # Should receive both chunks — BaseHTTPMiddleware would buffer and
    # potentially only yield the full body at once
    assert len(chunks) >= 2
    assert "chunk1" in chunks[0]
    assert "chunk2" in chunks[1]


@pytest.mark.asyncio
async def test_request_state_request_id_accessible_in_error_handlers():
    """request.state.request_id must be accessible in error handlers after
    the raw ASGI middleware rewrite.

    The middleware sets scope["state"]["request_id"] which Starlette's
    Request.state wraps via _State attribute delegation.
    """
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    from httpx import ASGITransport, AsyncClient
    from src.utils.middleware import add_request_monitoring

    app = FastAPI()
    add_request_monitoring(app)

    @app.get("/fail")
    async def fail():
        raise RuntimeError("boom")

    @app.exception_handler(RuntimeError)
    async def handler(request: Request, exc: RuntimeError):
        rid = getattr(request.state, "request_id", "MISSING")
        return JSONResponse(status_code=500, content={"request_id": rid})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/fail")
        assert resp.status_code == 500
        data = resp.json()
        assert data["request_id"] != "MISSING"
        assert len(data["request_id"]) > 0
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/utils/test_middleware.py::test_sse_streaming_not_broken_by_middleware -v`
Expected: FAIL or timeout — BaseHTTPMiddleware buffers the streaming response.

**Step 3: Write minimal implementation**

Rewrite `backend/src/utils/middleware.py` as raw ASGI middleware:

```python
"""Shared ASGI middleware for the main backend."""
from __future__ import annotations

import time
from uuid import uuid4

from fastapi import FastAPI
from starlette.types import ASGIApp, Receive, Scope, Send

from src.utils.logger import get_logger


class RequestMonitorMiddleware:
    """Raw ASGI middleware that logs every request with timing and request_id.

    Unlike BaseHTTPMiddleware, this does NOT buffer the response body,
    so SSE / chunked streaming and large downloads work correctly.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = None
        for key, value in scope.get("headers", []):
            if key == b"x-request-id":
                request_id = value.decode()
                break
        if request_id is None:
            request_id = str(uuid4())

        scope.setdefault("state", {})
        scope["state"]["request_id"] = request_id

        method = scope.get("method", "?")
        path = scope.get("path", "?")
        start = time.perf_counter()
        status = 500

        async def send_wrapper(message):
            nonlocal status
            if message["type"] == "http.response.start":
                # Append to the header list — ASGI headers are a list of
                # 2-tuples specifically to allow duplicate keys (e.g.
                # multiple Set-Cookie). Do NOT convert to dict.
                message["headers"] = list(message.get("headers", []))
                message["headers"].append((b"x-request-id", request_id.encode()))
                status = message.get("status", 500)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            status = 500
            raise
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            get_logger().info(
                "{method} {path} -> {status} ({elapsed:.1f}ms) [rid={request_id}]",
                method=method,
                path=path,
                status=status,
                elapsed=elapsed_ms,
                request_id=request_id,
            )


def add_request_monitoring(app: FastAPI) -> None:
    """Register the request monitoring middleware on a FastAPI app."""
    app.add_middleware(RequestMonitorMiddleware)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/utils/test_middleware.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/utils/middleware.py backend/tests/utils/test_middleware.py
git commit -m "fix(backend): convert RequestMonitorMiddleware to raw ASGI

BaseHTTPMiddleware buffers the full response body in memory, which
breaks SSE/chunked streaming endpoints like POST /chat/sessions/{id}/stream.
Rewritten as raw ASGI middleware that passes through streaming responses."
```

---

### Task 8: Type `source_span` on TrackSpan — replace bare dict

**Files:**
- Modify: `backend/src/core/visualize_evidence_with_expert_in_loop/contracts.py:108-116`
- Test: `backend/tests/core/visualize_evidence_with_expert_in_loop/test_contracts.py`

**Step 1: Write the failing test**

```python
"""Tests for SourceSpanDict typed contract."""
from __future__ import annotations

from src.core.visualize_evidence_with_expert_in_loop.contracts import SourceSpanDict, TrackSpan


def test_track_span_source_span_is_typed():
    """TrackSpan.source_span should use SourceSpanDict, not bare dict."""
    import inspect
    sig = inspect.signature(TrackSpan)
    source_span_type = sig.parameters["source_span"].annotation
    assert source_span_type is not dict


def test_source_span_dict_fields():
    """SourceSpanDict should accept known source span keys."""
    span = SourceSpanDict(
        text_snippet="some text",
        start_offset=0,
        end_offset=10,
        page=1,
    )
    assert span["text_snippet"] == "some text"
    assert span["page"] == 1
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_contracts.py -v`
Expected: FAIL — `source_span` is typed as `dict`.

**Step 3: Write minimal implementation**

Add `SourceSpanDict` to `contracts.py` (after imports, before `ReviewStatus`):

```python
from typing import TypedDict

class SourceSpanDict(TypedDict, total=False):
    """Structured source span stored in JSONB.

    This is a partial contract — the extraction pipeline may write
    additional keys (e.g. block_type, confidence, source_url).
    total=False allows extra keys at runtime; this TypedDict documents
    the known queryable fields used by the API layer.
    """

    text_snippet: str
    start_offset: int
    end_offset: int
    page: int | None
```

Update `TrackSpan`:
```python
    source_span: SourceSpanDict
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_contracts.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/visualize_evidence_with_expert_in_loop/contracts.py backend/tests/core/visualize_evidence_with_expert_in_loop/test_contracts.py
git commit -m "fix(backend): type source_span as SourceSpanDict instead of bare dict

TrackSpan.source_span was declared as dict, violating project rule 22.
Now uses a TypedDict with known keys: text_snippet, start_offset,
end_offset, page."
```

---

### Task 9: Type health endpoint return — replace bare dict

**Files:**
- Modify: `backend/app/main.py:106-109`
- Test: `backend/tests/api/test_health_endpoint.py`

**Step 1: Write the failing test**

```python
"""Tests for health endpoint type safety."""
from __future__ import annotations

import inspect


def test_health_endpoint_returns_basemodel():
    """Health endpoint should return a BaseModel, not bare dict."""
    from app.main import create_app
    app = create_app()
    for route in app.routes:
        if hasattr(route, "path") and route.path == "/health":
            ret = inspect.signature(route.endpoint).return_annotation
            assert ret is not dict, "Health endpoint should not return bare dict"
            break
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/api/test_health_endpoint.py -v`
Expected: FAIL — health returns `dict[str, str]`.

**Step 3: Write minimal implementation**

Add to `backend/app/main.py` (after existing imports):

```python
from pydantic import BaseModel

class HealthResponse(BaseModel):
    """Health check response."""
    status: str
```

Note: there is no naming conflict in `main.py` — no other `BaseModel` import exists.

Update the health endpoint:
```python
@_app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/api/test_health_endpoint.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/main.py backend/tests/api/test_health_endpoint.py
git commit -m "fix(backend): return HealthResponse model from /health endpoint

Replaces bare dict[str, str] return type with a Pydantic BaseModel
to comply with project rule 22 (no bare dict return types)."
```

---

### Task 10: Compile regex patterns at module level in `_detect_intent`

**Files:**
- Modify: `backend/src/core/visualize_evidence_with_expert_in_loop/chat_service.py:221-258`
- Test: `backend/tests/core/visualize_evidence_with_expert_in_loop/test_chat_service.py`

**Step 1: Write the failing test**

```python
def test_detect_intent_uses_module_level_compiled_patterns():
    """Regex patterns should be compiled at module level, not per call."""
    import src.core.visualize_evidence_with_expert_in_loop.chat_service as mod
    assert hasattr(mod, "_QUESTION_PATTERNS")
    assert hasattr(mod, "_CORRECTION_PATTERNS")
    assert all(hasattr(p, "search") for p in mod._QUESTION_PATTERNS)
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_chat_service.py::test_detect_intent_uses_module_level_compiled_patterns -v`
Expected: FAIL — no module-level compiled patterns.

**Step 3: Write minimal implementation**

Add at module level in `chat_service.py`:

```python
import re

_QUESTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p) for p in [
        r"\?", r"\bwhat\b", r"\bwhy\b", r"\bhow\b", r"\bwhich\b",
        r"\b什么\b", r"\b为什么\b", r"\b如何\b",
    ]
]
_CORRECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p) for p in [
        r"\bchange\b.*\bto\b", r"\bupdate\b.*\bto\b", r"\bcorrect\b.*\bto\b",
        r"\b修改\b.*\b为\b", r"\b改为\b",
    ]
]
```

Update `_detect_intent` to use compiled patterns:
```python
def _detect_intent(self, message: str) -> str:
    msg_lower = message.lower()
    if any(p.search(msg_lower) for p in _QUESTION_PATTERNS):
        return "question"
    if any(p.search(msg_lower) for p in _CORRECTION_PATTERNS):
        return "correction"
    return "note"
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_chat_service.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/visualize_evidence_with_expert_in_loop/chat_service.py backend/tests/core/visualize_evidence_with_expert_in_loop/test_chat_service.py
git commit -m "fix(backend): compile _detect_intent regex patterns at module level"
```

---

### Task 11: Add foreign key constraints to ChatMessage.evidence_id and entity_id

**Files:**
- Modify: `backend/src/dao/postgresql/models.py:515-522`
- Create: Alembic migration
- Test: `backend/tests/dao/test_chat_message_fk.py`

**Step 1: Write the failing test**

```python
"""Tests for ChatMessage foreign key constraints."""
from __future__ import annotations

from src.dao.postgresql.models import ChatMessage


def test_chat_message_evidence_id_has_foreign_key():
    """ChatMessage.evidence_id should reference canonical_evidence_items."""
    cols = ChatMessage.__table__.columns
    evidence_col = cols["evidence_id"]
    fk_tables = {fk.column.table.name for fk in evidence_col.foreign_keys}
    assert "canonical_evidence_items" in fk_tables


def test_chat_message_entity_id_has_foreign_key():
    """ChatMessage.entity_id should reference normalized_entities."""
    cols = ChatMessage.__table__.columns
    entity_col = cols["entity_id"]
    fk_tables = {fk.column.table.name for fk in entity_col.foreign_keys}
    assert "normalized_entities" in fk_tables
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/dao/test_chat_message_fk.py -v`
Expected: FAIL — `evidence_id` and `entity_id` have no foreign keys.

**Step 3: Write minimal implementation**

Update `ChatMessage` in `models.py`:

```python
evidence_id: Mapped[uuid.UUID | None] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("canonical_evidence_items.canonical_evidence_id"),
    nullable=True,
)
entity_id: Mapped[uuid.UUID | None] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("normalized_entities.entity_id"),
    nullable=True,
)
```

Generate Alembic migration (alembic.ini is at `database/migrations/`):
```bash
cd database/migrations && uv run alembic revision --autogenerate -m "add_fk_chat_message_evidence_entity"
```

Review the generated migration. Before the `op.create_foreign_key` calls, add cleanup SQL to remove orphaned references that would violate the new constraints:

```python
def upgrade() -> None:
    # Clean orphaned references before adding FK constraints
    op.execute("""
        DELETE FROM chat_messages
        WHERE evidence_id IS NOT NULL
          AND evidence_id NOT IN (SELECT canonical_evidence_id FROM canonical_evidence_items)
    """)
    op.execute("""
        DELETE FROM chat_messages
        WHERE entity_id IS NOT NULL
          AND entity_id NOT IN (SELECT entity_id FROM normalized_entities)
    """)
    # Then the autogenerate FK additions follow...
```

For the downgrade, the autogenerate `op.drop_constraint` calls are sufficient.

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/dao/test_chat_message_fk.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/dao/postgresql/models.py database/migrations/versions/ backend/tests/dao/test_chat_message_fk.py
git commit -m "fix(backend): add FK constraints to ChatMessage.evidence_id and entity_id"
```

---

### Task 12: Add `response_model` to Phase 4 API routes

**Files:**
- Modify: `backend/src/api/v1/evidence.py`
- Modify: `backend/src/api/v1/chat.py`
- Modify: `backend/src/api/v1/delta_audit.py`
- Modify: `backend/src/api/v1/source_link.py`
- Modify: `backend/src/core/visualize_evidence_with_expert_in_loop/contracts.py`
- Test: `backend/tests/api/test_response_models.py`

**Step 1: Write the failing test**

```python
"""Tests for API route response_model declarations."""
from __future__ import annotations


def test_all_v1_routes_declare_response_model():
    """All API v1 routes should declare response_model per project rule 22."""
    from app.main import create_app
    app = create_app()

    routes_without_model = []
    for route in app.routes:
        if not hasattr(route, "path") or not route.path.startswith("/api/v1"):
            continue
        if getattr(route, "response_model", None) is None:
            methods = ",".join(route.methods or [])
            routes_without_model.append(f"{methods} {route.path}")

    assert routes_without_model == [], f"Routes missing response_model: {routes_without_model}"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/api/test_response_models.py -v`
Expected: FAIL — several routes lack `response_model`.

**Step 3: Write minimal implementation**

Add `PatchResultResponse` to `contracts.py`:

```python
class PatchResultResponse(BaseModel):
    """API response for PATCH /evidence."""
    canonical_evidence_id: UUID
    old_status: ReviewStatus
    new_status: ReviewStatus
    deltas: int
    field_deltas: list[DeltaEntry]
```

Update each route:

`evidence.py`:
```python
@router.patch("/{canonical_evidence_id}", response_model=PatchResultResponse)
async def patch_evidence(...) -> PatchResultResponse:
    ...
    return PatchResultResponse(
        canonical_evidence_id=result.canonical_evidence_id,
        old_status=result.old_status,
        new_status=result.new_status,
        deltas=result.deltas,
        field_deltas=result.field_deltas,
    )
```

`chat.py`:
```python
@router.post("/sessions", response_model=ChatSessionResponse)
@router.get("/sessions/{processing_run_id}", response_model=list[ChatSessionResponse])
@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageResponse])
@router.post("/sessions/{session_id}/messages", response_model=ChatMessageResponse)
# stream_reply intentionally has NO response_model — it returns
# StreamingResponse (media_type="text/event-stream"), not a Pydantic model.
```

Note: The `stream_reply` endpoint returns `StreamingResponse`, which is not a Pydantic model. It must be excluded from the response_model check. Update the test to exclude streaming routes:

```python
STREAMING_ROUTES = {"GET /api/v1/chat/sessions/{session_id}/stream"}

routes_without_model = []
for route in app.routes:
    if not hasattr(route, "path") or not route.path.startswith("/api/v1"):
        continue
    methods = ",".join(route.methods or [])
    route_key = f"{methods} {route.path}"
    if route_key in STREAMING_ROUTES:
        continue
    if getattr(route, "response_model", None) is None:
        routes_without_model.append(route_key)
```

`delta_audit.py`:
```python
@router.get("/", response_model=list[ReviewAuditEventResponse])
```

`source_link.py`:
```python
@router.get("/{canonical_evidence_id}/bilingual", response_model=BilingualSpan)
@router.get("/{canonical_evidence_id}/{track}", response_model=TrackSpan | None)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/api/test_response_models.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/api/v1/evidence.py backend/src/api/v1/chat.py backend/src/api/v1/delta_audit.py backend/src/api/v1/source_link.py backend/src/core/visualize_evidence_with_expert_in_loop/contracts.py backend/tests/api/test_response_models.py
git commit -m "fix(backend): add response_model to all Phase 4 API routes"
```

---

### Task 13: Add API route tests for evidence, chat, delta_audit, source_link

**Files:**
- Create: `backend/tests/api/test_evidence_api.py`
- Create: `backend/tests/api/test_chat_api.py`
- Create: `backend/tests/api/test_delta_audit_api.py`
- Create: `backend/tests/api/test_source_link_api.py`

**Note:** These tests use the `async_client` fixture from `tests/api/conftest.py`, which creates `Settings()` with default values (i.e. `api_key=""`, auth disabled). After Task 2 adds auth, write routes still work in tests because no key is configured. This is intentional — the auth-specific behavior is tested separately in `test_auth.py`.

**Step 1: Write evidence API tests**

```python
"""Tests for evidence API routes."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_patch_evidence_returns_updated_card(async_client: AsyncClient):
    """PATCH /api/v1/evidence/{id} applies patch and returns result."""
    from src.core.visualize_evidence_with_expert_in_loop.contracts import ReviewStatus
    from src.core.visualize_evidence_with_expert_in_loop.feedback_service import PatchResult

    evidence_id = uuid4()
    mock_result = PatchResult(
        canonical_evidence_id=evidence_id,
        old_status=ReviewStatus.PROVISIONAL,
        new_status=ReviewStatus.CORRECTED,
        deltas=1,
        field_deltas=[],
    )

    # Patch in the route module where get_phase4_factory is bound
    with patch("src.api.v1.evidence.get_phase4_factory") as mock_factory:
        mock_service = MagicMock()
        mock_service.patch_evidence = AsyncMock(return_value=mock_result)
        mock_factory.return_value.create_feedback_service.return_value = mock_service

        response = await async_client.patch(
            f"/api/v1/evidence/{evidence_id}",
            json={"fields": {"gene": "BRCA1"}, "change_reason": "test"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["canonical_evidence_id"] == str(evidence_id)
        assert data["new_status"] == "corrected"


@pytest.mark.asyncio
async def test_patch_evidence_404_for_unknown(async_client: AsyncClient):
    """PATCH /api/v1/evidence/{id} returns 404 for unknown evidence."""
    from sqlalchemy.exc import NoResultFound

    with patch("src.api.v1.evidence.get_phase4_factory") as mock_factory:
        mock_service = MagicMock()
        mock_service.patch_evidence = AsyncMock(side_effect=NoResultFound())
        mock_factory.return_value.create_feedback_service.return_value = mock_service

        response = await async_client.patch(
            f"/api/v1/evidence/{uuid4()}",
            json={"fields": {"gene": "BRCA1"}},
        )
        assert response.status_code == 404
```

**Step 2: Write chat API tests**

```python
"""Tests for chat API routes."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_session(async_client: AsyncClient):
    """POST /api/v1/chat/sessions creates a session."""
    from src.core.visualize_evidence_with_expert_in_loop.contracts import ChatSessionResponse

    run_id = uuid4()
    session_id = uuid4()
    mock_response = ChatSessionResponse(
        chat_session_id=session_id,
        processing_run_id=run_id,
        user_id=None,
        created_at="2026-06-01T00:00:00Z",
        message_count=0,
    )

    with patch("src.api.v1.chat.get_phase4_factory") as mock_factory:
        mock_service = MagicMock()
        mock_service.create_session = AsyncMock(return_value=mock_response)
        mock_factory.return_value.create_chat_service.return_value = mock_service

        response = await async_client.post(
            "/api/v1/chat/sessions",
            json={"processing_run_id": str(run_id)},
        )
        assert response.status_code == 200
        assert response.json()["chat_session_id"] == str(session_id)


@pytest.mark.asyncio
async def test_append_message(async_client: AsyncClient):
    """POST /api/v1/chat/sessions/{id}/messages appends a message."""
    from src.core.visualize_evidence_with_expert_in_loop.contracts import ChatMessageResponse

    session_id = uuid4()
    msg_id = uuid4()
    mock_response = ChatMessageResponse(
        message_id=msg_id,
        chat_session_id=session_id,
        role="user",
        content="What is the gene?",
        evidence_id=None,
        entity_id=None,
        created_at="2026-06-01T00:00:00Z",
    )

    with patch("src.api.v1.chat.get_phase4_factory") as mock_factory:
        mock_service = MagicMock()
        mock_service.append_message = AsyncMock(return_value=mock_response)
        mock_service.generate_reply = AsyncMock(return_value=None)
        mock_factory.return_value.create_chat_service.return_value = mock_service

        response = await async_client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={"role": "user", "content": "What is the gene?"},
        )
        assert response.status_code == 200
        assert response.json()["content"] == "What is the gene?"
```

**Step 3: Write delta_audit and source_link API tests**

```python
# test_delta_audit_api.py
"""Tests for delta audit API routes."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_audit_events(async_client: AsyncClient):
    """GET /api/v1/delta-audit/ returns audit events."""
    with patch("src.api.v1.delta_audit.get_phase4_factory") as mock_factory:
        mock_service = MagicMock()
        mock_service.list_audit_events = AsyncMock(return_value=[])
        mock_factory.return_value.delta_audit = mock_service

        response = await async_client.get("/api/v1/delta-audit/")
        assert response.status_code == 200
        assert response.json() == []
```

```python
# test_source_link_api.py
"""Tests for source link API routes."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_bilingual_span(async_client: AsyncClient):
    """GET /api/v1/source-link/{id}/bilingual returns bilingual span."""
    from src.core.visualize_evidence_with_expert_in_loop.contracts import BilingualSpan

    evidence_id = uuid4()
    mock_response = BilingualSpan(
        canonical_evidence_id=evidence_id,
        original_track=None,
        translated_track=None,
        alignment_confidence=None,
    )

    with patch("src.api.v1.source_link.get_phase4_factory") as mock_factory:
        mock_linker = MagicMock()
        mock_linker.get_bilingual_span = AsyncMock(return_value=mock_response)
        mock_factory.return_value.create_source_linker.return_value = mock_linker

        response = await async_client.get(
            f"/api/v1/source-link/{evidence_id}/bilingual"
        )
        assert response.status_code == 200
        assert response.json()["canonical_evidence_id"] == str(evidence_id)
```

**Step 4: Run all new tests**

Run: `cd backend && uv run pytest tests/api/test_evidence_api.py tests/api/test_chat_api.py tests/api/test_delta_audit_api.py tests/api/test_source_link_api.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/tests/api/test_evidence_api.py backend/tests/api/test_chat_api.py backend/tests/api/test_delta_audit_api.py backend/tests/api/test_source_link_api.py
git commit -m "test(backend): add API route tests for evidence, chat, delta_audit, source_link"
```

---

### Task 14: Wire MinerU config fields through to parsers

**Files:**
- Modify: `backend/src/api/wiring.py:88-89`
- Test: `backend/tests/api/test_wiring_config.py`

**Step 1: Write the failing test**

```python
"""Tests for wiring config propagation to parsers."""
from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_remote_parser_receives_all_config():
    """MinerURemoteParser should receive poll_interval and max_poll_attempts."""
    with patch("src.api.wiring.get_config") as mock_cfg, \
         patch("src.api.wiring.get_session_factory"), \
         patch("src.api.wiring.DocumentAcquisitionService"), \
         patch("src.api.wiring.MinerURemoteParser") as mock_remote, \
         patch("src.api.wiring.MinerULocalParser"), \
         patch("src.api.wiring.DocumentParseOrchestrator"), \
         patch("src.api.wiring.ParseDocumentService"), \
         patch("src.api.wiring.TranslationService"), \
         patch("src.api.wiring.EvidenceExtractionService"), \
         patch("src.api.wiring.EntityStandardizationService"), \
         patch("src.api.wiring.PipelineOrchestrator"), \
         patch("src.api.wiring.PipelineSemaphore"), \
         patch("src.api.wiring.PipelineRunner"), \
         patch("src.api.wiring.SessionBoundStatePersistence"), \
         patch("src.api.wiring.RetryablePhaseExecutor"), \
         patch("src.api.wiring.Phase1Adapter"), \
         patch("src.api.wiring.Phase2Adapter"), \
         patch("src.api.wiring.Phase3Adapter"), \
         patch("src.api.wiring.Phase4ServiceFactory"), \
         patch("src.api.wiring.set_pipeline_runner"), \
         patch("src.api.wiring.set_phase4_factory"):

        mock_cfg.return_value = MagicMock(
            mineru_api_token="fallback-token",
            parse_document=MagicMock(
                mineru_remote_api_token="remote-token",
                mineru_remote_poll_interval=3.0,
                mineru_remote_max_poll_attempts=200,
                mineru_local_model_server_url="http://localhost:8002",
                mineru_local_model_id="test-model",
                mineru_local_timeout=60.0,
                mineru_local_dpi=300,
            ),
        )

        from src.api.wiring import wire_dependencies
        wire_dependencies()

        # Verify MinerURemoteParser received the parse_document config values
        call_kwargs = mock_remote.call_args
        assert call_kwargs is not None
        _, kwargs = call_kwargs
        assert kwargs.get("api_token") == "remote-token"
        assert kwargs.get("poll_interval") == 3.0
        assert kwargs.get("max_poll_attempts") == 200


def test_local_parser_receives_all_config():
    """MinerULocalParser should receive model_server_url, model_id, timeout, dpi."""
    with patch("src.api.wiring.get_config") as mock_cfg, \
         patch("src.api.wiring.get_session_factory"), \
         patch("src.api.wiring.DocumentAcquisitionService"), \
         patch("src.api.wiring.MinerURemoteParser"), \
         patch("src.api.wiring.MinerULocalParser") as mock_local, \
         patch("src.api.wiring.DocumentParseOrchestrator"), \
         patch("src.api.wiring.ParseDocumentService"), \
         patch("src.api.wiring.TranslationService"), \
         patch("src.api.wiring.EvidenceExtractionService"), \
         patch("src.api.wiring.EntityStandardizationService"), \
         patch("src.api.wiring.PipelineOrchestrator"), \
         patch("src.api.wiring.PipelineSemaphore"), \
         patch("src.api.wiring.PipelineRunner"), \
         patch("src.api.wiring.SessionBoundStatePersistence"), \
         patch("src.api.wiring.RetryablePhaseExecutor"), \
         patch("src.api.wiring.Phase1Adapter"), \
         patch("src.api.wiring.Phase2Adapter"), \
         patch("src.api.wiring.Phase3Adapter"), \
         patch("src.api.wiring.Phase4ServiceFactory"), \
         patch("src.api.wiring.set_pipeline_runner"), \
         patch("src.api.wiring.set_phase4_factory"):

        mock_cfg.return_value = MagicMock(
            mineru_api_token="fallback",
            parse_document=MagicMock(
                mineru_remote_api_token="",
                mineru_remote_poll_interval=2.0,
                mineru_remote_max_poll_attempts=150,
                mineru_local_model_server_url="http://localhost:8002",
                mineru_local_model_id="test-model-id",
                mineru_local_timeout=60.0,
                mineru_local_dpi=300,
            ),
        )

        from src.api.wiring import wire_dependencies
        wire_dependencies()

        _, kwargs = mock_local.call_args
        assert kwargs.get("model_server_url") == "http://localhost:8002"
        assert kwargs.get("model_id") == "test-model-id"
        assert kwargs.get("timeout") == 60.0
        assert kwargs.get("dpi") == 300
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/api/test_wiring_config.py -v`
Expected: FAIL — current wiring only passes `cfg.mineru_api_token`.

**Step 3: Write minimal implementation**

Update `backend/src/api/wiring.py:88-89`:

```python
    pd_cfg = cfg.parse_document
    remote_parser = MinerURemoteParser(
        api_token=pd_cfg.mineru_remote_api_token or cfg.mineru_api_token,
        poll_interval=pd_cfg.mineru_remote_poll_interval,
        max_poll_attempts=pd_cfg.mineru_remote_max_poll_attempts,
    )
    local_parser = MinerULocalParser(
        model_server_url=pd_cfg.mineru_local_model_server_url,
        model_id=pd_cfg.mineru_local_model_id,
        timeout=pd_cfg.mineru_local_timeout,
        dpi=pd_cfg.mineru_local_dpi,
    )
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/api/test_wiring_config.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/api/wiring.py backend/tests/api/test_wiring_config.py
git commit -m "fix(backend): wire MinerU config fields through to parsers

MINERU_REMOTE_API_TOKEN, poll_interval, max_poll_attempts,
local_model_server_url, model_id, timeout, and DPI were defined in
config but never passed to the parser constructors."
```

---

### Task 15: Declare model-server direct dependencies as optional extra

**Files:**
- Modify: `backend/pyproject.toml`

**Context:** The model-server runs as a standalone script (`uv run python main.py`) using the backend's venv, but `vllm` (~2GB with CUDA) should not be pulled for every backend installation. Use `[project.optional-dependencies]` to keep it opt-in.

**Step 1: Add optional model-server extra**

Add to `backend/pyproject.toml` under `[project.optional-dependencies]`:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.2.0",
    "pytest-asyncio>=0.23.0",
    "httpx>=0.27.0",
    "ruff>=0.5.0",
]
model-server = [
    "vllm>=0.8.0",
    "numpy>=1.26.0",
    "pillow>=10.0.0",
]
```

Also add `pillow>=10.0.0` to the main `dependencies` list (it is directly imported by `backend/src/core/ingest_and_digitize_data/parse_document/local/parser.py` and transitively required by `pymupdf`, but project rule 1 requires explicit declaration for direct imports). `vllm` and `numpy` stay in `model-server` only.

**Step 2: Update lock file**

Run: `cd backend && uv lock`

**Step 3: Verify model-server imports resolve with the extra**

Run: `cd backend && uv pip install -e ".[model-server]" && uv run python -c "import vllm; import numpy; from PIL import Image; print('OK')"`
Expected: OK

**Step 4: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock
git commit -m "chore(backend): declare model-server deps as optional extra

vllm, numpy are model-server-specific (~2GB with CUDA) and should not
be pulled for every backend installation. Added [project.optional-dependencies]
model-server extra. Pillow added to main dependencies (direct import in
parse_document/local/parser.py)."
```

---

### Task 16: Tighten .gitignore for database config files

**Files:**
- Modify: `.gitignore`

**Step 1: Add precise ignore rules**

Append to `.gitignore`:

```
# Database config (may contain credentials)
database/config/.env
database/config/.env.*
!database/config/.env.example
```

**Step 2: Remove .env.neo4j from tracking**

```bash
git rm --cached database/config/.env.neo4j
```

**Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: stop tracking database/config/.env.neo4j, tighten gitignore

.env.neo4j was tracked by git. Added precise ignore pattern that
covers .env and .env.* but explicitly preserves .env.example."
```

---

## Execution Notes

### Task Dependency Order

```
Task 1 (session commit) ──┐
                           ├──► Task 13 (API route tests — depend on commit fix + auth)
Task 2 (auth)             ──┘
Task 3 (upsert)           — independent
Task 4 (LRU cache)        — independent
Task 5 (httpx reuse)      — independent
Task 6 (VLM unload)       — independent (model-server tests)
Task 7 (SSE middleware)   — independent
Task 8 (source_span type) ──┐
                             ├──► Task 12 (response_model — depends on PatchResultResponse)
Task 9 (health type)       ──┘
Task 10 (regex compile)    — independent
Task 11 (ChatMessage FK)   — independent (needs Alembic + DB)
Task 14 (MinerU config)    — independent
Task 15 (model-server deps)— independent
Task 16 (.gitignore)       — independent
```

### Workflow Steps Per Task

Each task must follow this workflow:
1. Write the failing test → verify it fails
2. Write the minimal implementation → verify it passes
3. Run the full test suite: `cd backend && uv run pytest tests/ -x -q`
4. Update `progress.txt` with task completion
5. If the fix involved trial-and-error debugging, record in `lesson.md`
6. Commit using conventional commits format

### Post-Execution Steps

After all tasks are complete:
1. Run full lint: `cd backend && uv run ruff check app src services/model-server/app`
2. Run full test suite: `cd backend && uv run pytest tests/ -q`
3. Run model-server tests: `cd backend/services/model-server && uv run pytest tests/ -q`
4. Update `progress.txt` with overall completion
5. Use `skill:doc-organize` if any docs/ directory changes were made
6. Use `skill:module-guide` if any new modules were created (auth.py)

### Estimated Effort

~3-4 hours total. Each task is 5-20 minutes. Tasks 1, 2, 5, 7 are the most complex.
