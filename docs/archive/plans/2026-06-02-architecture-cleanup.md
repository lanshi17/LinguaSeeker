# Backend Architecture Cleanup: Enforcing api→agents→core→dao Layering

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Eliminate direct API→core dependencies, add Phase 4 agents layer, unify session factory/engine, merge redundant modules, and remove workaround code.

**Architecture:** Strict unidirectional `api → agents → core → dao` dependency. API routes handle only HTTP concerns (param parsing, status codes, response models) and delegate to core services via the agents layer's factory/adapters. Phases 1-3 retain the LangGraph pipeline pattern; Phase 4 uses a thin factory delegate pattern (not in the graph). Long-lived dependencies (cfg, LLM client) are injected at the wiring layer; short-lived dependencies (AsyncSession) are created via factory or passed as method parameters.

**Tech Stack:** FastAPI + Pydantic + SQLAlchemy async + LangGraph

---

## Design Decisions Quick Reference

| Decision | Resolution | Rationale |
|---|---|---|
| Scope | `backend/src/` + `backend/app/` | model-server is an independent microservice — untouched; frontend untouched; libs untouched |
| Phase 4 agents pattern | thin factory delegate | Phase 4 is interactive request-response, not suited for LangGraph nodes |
| Phase 4 service lifecycle | per-request, via factory | Service constructors require AsyncSession |
| app/main.py DI | extract to `src/api/wiring.py` | lifespan should only manage lifecycle events |
| state_persistence | merge into one file, two classes | `DirectStatePersistence` (tests) + `SessionBoundStatePersistence` (prod) |
| SessionBoundStandardizationService | eliminate; pass session as method param | root-cause fix, not a wrapper |
| DAO boundary | deferred (P2) | pure physical relocation, no decoupling benefit at this stage |
| Test strategy | update alongside refactor, coverage must not drop | import paths and mock targets will change |

---

## Current Problem Inventory

```
A. API layer directly instantiates core services ← P0
   src/api/v1/evidence.py:29 → FeedbackService(session)
   src/api/v1/chat.py:43 → ChatService(session)
   src/api/v1/delta_audit.py:32 → DeltaAuditService()
   src/api/v1/source_link.py:27 → SourceLinker(session)

B. Phase 4 has no agents layer ← P0
   src/agents/ only contains phase_1/2/3_adapter.py

C. deps.py and main.py each create independent engines ← P0 (new)
   deps.py:15-21 → _get_session_factory() lazy-inits engine (actual engine creation at line 19)
   main.py:58-59 → lifespan calls build_async_engine(cfg) + async_session_factory(engine)
   Result: two connection pools, two transaction isolation scopes

D. EntityStandardizationService constructor binds session ← P1
   src/core/standardize_entities_and_align_knowledge/api.py:102
   → def __init__(self, cfg, session) forces the SessionBoundStandardizationService wrapper

E. state_persistence — two files doing the same thing ← P1
   state_persistence.py → StatePersistenceService(session) for tests (will be renamed to DirectStatePersistence)
   state_persistence_factory.py → SessionBoundPersistence(session_factory) for prod

F. app/main.py lifespan ~100 lines of DI logic ← P1
   should be extracted to a dedicated module

G. DAO boundary blur ← P2 (deferred)
   standardization repositories live in core/ instead of dao/

H. Service facade naming inconsistency ← P2 (deferred)
   api.py / service.py / workflow.py used interchangeably

I. delta_audit.py directly imports DAO model ← P2 (deferred, documented)
   src/api/v1/delta_audit.py:19 → from src.dao.postgresql.models import ReviewAuditEvent
   Used in _to_response() for ORM→API conversion. Does not violate api→dao layering,
   but inconsistent with the contracts pattern (should use contract types, not raw ORM models).
```

---

### Task 0: Preparation — establish current test baseline

**Purpose:** Record the pre-refactor passing test count to ensure no regression.

**Step 1: Run full backend test suite**

```bash
cd backend && python -m pytest tests/ -x --tb=short 2>&1 | tail -20
```

**Step 2: Record baseline**

Write the passing test count to `progress.txt`:
```
[2026-06-02] Architecture cleanup baseline: NNN tests passed [baseline]
```

---

### Task 1: Unify session factory — eliminate dual engines in deps.py and main.py

**Files:**
- Modify: `backend/src/api/deps.py:1-28`
- Modify: `backend/app/main.py:22-100`
- Create: `backend/src/api/wiring.py`



**Why first:** This is the dependency for all subsequent changes — both the Phase 4 factory and Phase 3 adapter need the same `session_factory`. Unify the factory first, then build on top.

> **Note — circular import avoidance:** After Task 6, `wiring.py` will import from `deps.py` (`set_phase4_factory`). `deps.py` imports from `wiring.py` (`get_session_factory`). This circular reference is safe because the `deps.py` → `wiring.py` direction is evaluated first (Task 1), and the `wiring.py` → `deps.py` direction (Task 6) uses local imports inside `wire_dependencies()` which execute at call time, not module load time.

---

**Step 1: Create `src/api/wiring.py` — extract engine/session_factory creation**
```python
"""Application dependency wiring — single source of truth for engine & session factory."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.core.config import get_config
from src.dao.postgresql.connection import async_session_factory, build_async_engine

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Lazy-init and return the singleton session factory."""
    global _engine, _session_factory
    if _session_factory is None:
        _engine = build_async_engine(get_config())
        _session_factory = async_session_factory(_engine)
    return _session_factory


async def dispose_engine() -> None:
    """Teardown the engine (called from lifespan shutdown)."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
```

---

**Step 2: Modify `src/api/deps.py` — delegate to wiring.py**

Remove `_engine`, `_session_factory`, `_get_session_factory`, and `build_async_engine` import from `deps.py`. Import from wiring instead:

```python
"""API dependencies."""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.wiring import get_session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency: yield an async database session."""
    factory = get_session_factory()
    async with factory() as session:
        yield session
```

---

**Step 3: Modify `app/main.py` lifespan — use wiring's engine**

Replace in lifespan:
```python
cfg = get_config()
engine = build_async_engine(cfg)
session_factory = async_session_factory(engine)
```
with:
```python
from src.api.wiring import get_session_factory, dispose_engine
session_factory = get_session_factory()
```

Replace teardown `await engine.dispose()` with `await dispose_engine()`.

---

**Step 4: Verify with tests**

```bash
cd backend && python -m pytest tests/ -x --tb=short 2>&1 | tail -5
```

Expected: test count unchanged (matches baseline).

**Step 5: Commit**

```bash
git add backend/src/api/wiring.py backend/src/api/deps.py backend/app/main.py
git commit -m "refactor: unify session factory into wiring.py, eliminate dual engine"
```

---

### Task 2: Create Phase 4 agents-layer factory

**Files:**
- Create: `backend/src/agents/phase_4_factory.py`

**Purpose:** API routes must no longer `import` core services directly. All Phase 4 services are created through the factory.

---

**Step 1: Create `src/agents/phase_4_factory.py`**

```python
"""Phase 4 service factory — thin delegate between API and core services.

Phase 4 (evidence review, chat, audit, source linking) is interactive
request-response, not a LangGraph pipeline node.  This factory provides
the agents-layer boundary so API routes never import core services directly.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.visualize_evidence_with_expert_in_loop.chat_service import ChatService
from src.core.visualize_evidence_with_expert_in_loop.delta_audit_service import (
    DeltaAuditService,
)
from src.core.visualize_evidence_with_expert_in_loop.feedback_service import (
    FeedbackService,
)
from src.core.visualize_evidence_with_expert_in_loop.source_linker import SourceLinker


class Phase4ServiceFactory:
    """Creates Phase 4 services with per-request sessions.

    Long-lived dependencies (cfg) are injected at construction time.
    Short-lived dependencies (AsyncSession) are passed per-method-call.
    """

    def __init__(self, cfg: Any):
        self._cfg = cfg
        # DeltaAuditService is stateless — create once
        self._delta_audit = DeltaAuditService()

    def create_feedback_service(self, session: AsyncSession) -> FeedbackService:
        return FeedbackService(session)

    def create_chat_service(self, session: AsyncSession) -> ChatService:
        return ChatService(session)

    def create_source_linker(self, session: AsyncSession) -> SourceLinker:
        return SourceLinker(session)

    @property
    def delta_audit(self) -> DeltaAuditService:
        return self._delta_audit
```

---

**Step 2: Verify module is importable**

```bash
cd backend && python -c "from src.agents.phase_4_factory import Phase4ServiceFactory; print('OK')"
```

Expected: `OK`

**Step 3: Commit**

```bash
git add backend/src/agents/phase_4_factory.py
git commit -m "feat: add Phase4ServiceFactory as agents-layer boundary for Phase 4"
```

---

### Task 3: Refactor API layer — Phase 4 routes delegate through factory

**Files:**
- Modify: `backend/src/api/v1/evidence.py`
- Modify: `backend/src/api/v1/chat.py`
- Modify: `backend/src/api/v1/delta_audit.py`
- Modify: `backend/src/api/v1/source_link.py`
- Modify: `backend/src/api/deps.py` (add factory dependency injection)
- Modify: `backend/app/main.py` (create factory and inject)

---

**Step 1: Add `get_phase4_factory` dependency to `deps.py`**

```python
from src.agents.phase_4_factory import Phase4ServiceFactory

_phase4_factory: Phase4ServiceFactory | None = None


def set_phase4_factory(factory: Phase4ServiceFactory) -> None:
    global _phase4_factory
    _phase4_factory = factory


def get_phase4_factory() -> Phase4ServiceFactory:
    if _phase4_factory is None:
        raise RuntimeError("Phase4ServiceFactory not initialized")
    return _phase4_factory
```

---

**Step 2: Modify `src/api/v1/evidence.py` — use factory instead of direct instantiation**

The full updated import block:

```python
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session, get_phase4_factory
from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    EvidencePatchRequest,
)
from src.core.visualize_evidence_with_expert_in_loop.feedback_service import (
    PatchResult,
)
```

And the route body:
```python
@router.patch("/{canonical_evidence_id}")
async def patch_evidence(
    canonical_evidence_id: UUID,
    patch: EvidencePatchRequest,
    session: AsyncSession = Depends(get_db_session),
) -> PatchResult:
    """Apply a patch to an evidence card and record audit event."""
    factory = get_phase4_factory()
    service = factory.create_feedback_service(session)
    try:
        return await service.patch_evidence(
            canonical_evidence_id=canonical_evidence_id,
            patch=patch,
            reviewer_id=None,
        )
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Evidence not found")
```

Key change: `FeedbackService` is no longer imported; `PatchResult` (a dataclass) is retained.

---

**Step 3: Modify `src/api/v1/chat.py` — use factory**

```python
from src.api.deps import get_db_session, get_phase4_factory
# ... other imports unchanged ...
```

Route body pattern:
```python
factory = get_phase4_factory()
service = factory.create_chat_service(session)
```

Remove `from src.core.visualize_evidence_with_expert_in_loop.chat_service import ChatService`.

---

**Step 4: Modify `src/api/v1/delta_audit.py` — use factory**

```python
from src.api.deps import get_phase4_factory
# ... other imports unchanged ...
```

Route body:
```python
service = get_phase4_factory().delta_audit
```

Remove `from src.core.visualize_evidence_with_expert_in_loop.delta_audit_service import DeltaAuditService`.

---

**Step 5: Modify `src/api/v1/source_link.py` — use factory**

```python
from src.api.deps import get_db_session, get_phase4_factory
# ... other imports unchanged ...
```

Route body:
```python
factory = get_phase4_factory()
linker = factory.create_source_linker(session)
```

Remove `from src.core.visualize_evidence_with_expert_in_loop.source_linker import SourceLinker`.

---

**Step 6: Create and inject factory in `app/main.py` lifespan**

```python
from src.agents.phase_4_factory import Phase4ServiceFactory
from src.api.deps import set_phase4_factory

# In lifespan startup, near set_pipeline_runner:
phase4_factory = Phase4ServiceFactory(cfg=cfg)
set_phase4_factory(phase4_factory)
```

---

**Step 7: Run tests**

```bash
cd backend && python -m pytest tests/ -x --tb=short 2>&1 | tail -5
```

Expected: test count unchanged vs baseline (only API route import paths changed; no behavioral change).

**Step 8: Commit**

```bash
git add backend/src/api/v1/evidence.py backend/src/api/v1/chat.py \
        backend/src/api/v1/delta_audit.py backend/src/api/v1/source_link.py \
        backend/src/api/deps.py backend/app/main.py
git commit -m "refactor: Phase 4 API routes delegate through Phase4ServiceFactory"
```

---

### Task 4: Refactor EntityStandardizationService — eliminate SessionBound wrapper

**Files:**
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/api.py`
- Modify: `backend/src/agents/phase_3_adapter.py`
- Delete: `backend/src/agents/session_bound_standardization.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/agents/test_phase_3_adapter.py`

---

**Step 1: Modify `EntityStandardizationService.__init__` — remove session parameter**

Before (`api.py:102`):
```python
def __init__(self, cfg: Any, session: Any):
    self._cfg = cfg
    self._session = session
```

After:
```python
def __init__(self, cfg: Any):
    self._cfg = cfg
```

---

**Step 2: Modify `run_dual_result` signature — session as method parameter**

Before:
```python
async def run_dual_result(
    self,
    result: DualEvidenceExtractionResult,
    *,
    source_document_id: str,
    processing_run_id: str,
) -> StandardizationResult:
    repository = StandardizationRepository(self._session)
    ...
```

After:
```python
async def run_dual_result(
    self,
    session: Any,
    result: DualEvidenceExtractionResult,
    *,
    source_document_id: str,
    processing_run_id: str,
) -> StandardizationResult:
    repository = StandardizationRepository(session)
    ...
    matcher = HybridTerminologyMatcher(precise_matcher, similarity_matcher)
    adapter = DualResultAdapter()
    input_data = adapter.to_standardization_input(
        result,
        source_document_id=source_document_id,
        processing_run_id=processing_run_id,
    )
    return await StandardizationService(matcher, repository).run(input_data)
```

All internal `self._session` references must be replaced with the local `session` variable. **Critical:** `SimilarityTerminologyMatcher` construction also references `self._session` — must be updated in sync:

```python
# api.py ~line 126 — PgvectorTerminologyRepository also binds self._session
similarity_matcher = SimilarityTerminologyMatcher(
    ...
    repository=PgvectorTerminologyRepository(session),  # ← self._session → session
    ...
)
```

Full change set: `StandardizationRepository(self._session)` → `StandardizationRepository(session)`, `PgvectorTerminologyRepository(self._session)` → `PgvectorTerminologyRepository(session)`.

---

**Step 3: Modify `Phase3Adapter` — hold service + session_factory, manage session itself**

Before (`phase_3_adapter.py`):
```python
class Phase3Adapter:
    def __init__(self, standardization_service: EntityStandardizationService):
        self._standardization = standardization_service

    async def run(self, state):
        ...
        standardization_result = await self._standardization.run_dual_result(
            dual_result, ...
        )
```

After:
```python
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

class Phase3Adapter:
    def __init__(
        self,
        standardization_service: EntityStandardizationService,
        session_factory: async_sessionmaker[AsyncSession],
    ):
        self._standardization = standardization_service
        self._session_factory = session_factory

    async def run(self, state):
        ...
        async with self._session_factory() as session:
            standardization_result = await self._standardization.run_dual_result(
                session, dual_result, ...
            )
```

---

**Step 4: Delete `session_bound_standardization.py`**

```bash
rm backend/src/agents/session_bound_standardization.py
```

---

**Step 5: Update `app/main.py` lifespan — Phase3Adapter construction**

Before:
```python
from src.agents.session_bound_standardization import SessionBoundStandardizationService
standardization_service = SessionBoundStandardizationService(cfg=cfg, session_factory=session_factory)
phase_adapters = {
    ...
    "phase_3": Phase3Adapter(standardization_service),
}
```

After:
```python
from src.core.standardize_entities_and_align_knowledge.api import EntityStandardizationService
standardization_service = EntityStandardizationService(cfg=cfg)
phase_adapters = {
    ...
    "phase_3": Phase3Adapter(standardization_service, session_factory),
}
```

---

**Step 6: Update `Phase3Adapter` tests**


1. `Phase3Adapter` constructor signature changed (added `session_factory` parameter) — create a mock session factory at construction time:
   ```python
   mock_session = AsyncMock()
   mock_session_factory = MagicMock()
   mock_session_factory.return_value.__aenter__.return_value = mock_session
   adapter = Phase3Adapter(
       standardization_service=mock_standardization,
       session_factory=mock_session_factory,
   )
   ```
   *(Note: `MagicMock()` alone does not support `async with`; the `__aenter__` mock is required.)*
2. `mock_standardization.run_dual_result` signature changed (added `session` as first positional arg) — update `AsyncMock` call assertions to expect `mock_session` as first argument.

---

**Step 7: Run tests**

```bash
cd backend && python -m pytest tests/ -x --tb=short 2>&1 | tail -5
```

---

**Step 8: Commit**

```bash
git add backend/src/core/standardize_entities_and_align_knowledge/api.py \
        backend/src/agents/phase_3_adapter.py \
        backend/app/main.py \
        tests/agents/test_phase_3_adapter.py
git rm backend/src/agents/session_bound_standardization.py
git commit -m "refactor: pass session as method param to EntityStandardizationService, remove SessionBound wrapper"
```

---

### Task 5: Merge state_persistence into one file

**Files:**
- Modify: `backend/src/agents/state_persistence.py` (merge both classes)
- Delete: `backend/src/agents/state_persistence_factory.py`
- Modify: `backend/src/agents/orchestrator.py` (update import)
- Modify: `backend/src/agents/runner.py` (update import)
- Modify: `backend/app/main.py` (update import)
- Modify: `backend/tests/agents/test_state_persistence_layer.py` (update import)

---

**Step 1: Merge — add `SessionBoundStatePersistence` to `state_persistence.py`**

Rename the existing `StatePersistenceService` to `DirectStatePersistence`, append `SessionBoundStatePersistence`:

```python
"""State persistence layer for pipeline orchestrator.

Two implementations:
- DirectStatePersistence: binds a single session (unit tests).
- SessionBoundStatePersistence: session-per-operation (production).
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.agents.contracts import PipelineGraphState
from src.dao.postgresql.models import PipelineRunState


class DirectStatePersistence:
    """Save/load PipelineGraphState with a fixed session.

    Intended for unit tests with short-lived sessions only.
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, state: PipelineGraphState) -> None:
        existing = await self._session.get(
            PipelineRunState, UUID(state.processing_run_id)
        )
        state_json = state.model_dump(mode="json")
        if existing:
            existing.state_json = state_json
        else:
            new_record = PipelineRunState(
                processing_run_id=UUID(state.processing_run_id),
                source_document_id=UUID(state.source_document_id),
                state_json=state_json,
            )
            self._session.add(new_record)
        await self._session.commit()

    async def load(self, processing_run_id: str) -> Optional[PipelineGraphState]:
        record = await self._session.get(
            PipelineRunState, UUID(processing_run_id)
        )
        if record is None:
            return None
        return PipelineGraphState.model_validate(record.state_json)


class SessionBoundStatePersistence:
    """Save/load PipelineGraphState with session-per-operation.

    Creates a fresh session for each save()/load() call, avoiding
    stale-session bugs in long-lived contexts (production lifespan).
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory

    async def save(self, state: PipelineGraphState) -> None:
        async with self._session_factory() as session:
            existing = await session.get(
                PipelineRunState, UUID(state.processing_run_id)
            )
            state_json = state.model_dump(mode="json")
            if existing:
                existing.state_json = state_json
            else:
                new_record = PipelineRunState(
                    processing_run_id=UUID(state.processing_run_id),
                    source_document_id=UUID(state.source_document_id),
                    state_json=state_json,
                )
                session.add(new_record)
            await session.commit()

    async def load(self, processing_run_id: str) -> Optional[PipelineGraphState]:
        async with self._session_factory() as session:
            record = await session.get(
                PipelineRunState, UUID(processing_run_id)
            )
            if record is None:
                return None
            return PipelineGraphState.model_validate(record.state_json)
```

---

**Step 2: Update all imports — orchestrator, runner, main, tests**

Since `StatePersistenceService` alias is removed, all consumers import the concrete class:

- `orchestrator.py`:
  - Remove `from src.agents.state_persistence import StatePersistenceService`
  - Replace with `from src.agents.state_persistence import SessionBoundStatePersistence`
  - `__init__` type annotation: `StatePersistenceService` → `SessionBoundStatePersistence`
- `runner.py`:
  - Same: type annotation → `SessionBoundStatePersistence`
- `app/main.py`: `from src.agents.state_persistence import SessionBoundStatePersistence`
- `tests/agents/test_state_persistence_layer.py`: `from src.agents.state_persistence import DirectStatePersistence`

---

**Step 3: Delete `state_persistence_factory.py`**

```bash
rm backend/src/agents/state_persistence_factory.py
```

---

**Step 4: Run tests**

```bash
cd backend && python -m pytest tests/agents/test_state_persistence*.py -x --tb=short
```

---

**Step 5: Commit**

```bash
git add backend/src/agents/state_persistence.py \
        backend/src/agents/orchestrator.py \
        backend/src/agents/runner.py \
        backend/app/main.py \
        tests/agents/test_state_persistence_layer.py
git rm backend/src/agents/state_persistence_factory.py
git commit -m "refactor: merge state_persistence_factory into state_persistence as SessionBoundStatePersistence"
```

---

### Task 6: Extract app/main.py lifespan DI into wiring.py

**Files:**
- Modify: `backend/src/api/wiring.py` (append `wire_dependencies` function)
- Modify: `backend/app/main.py` (lifespan reduced to ~10 lines)

---

**Step 1: Append `wire_dependencies(app)` to `wiring.py`**

```python
def wire_dependencies(app) -> None:
    """Assemble and inject all application dependencies.

    Called once from lifespan startup.  Creates the full service graph:
    engine → session_factory → adapters → orchestrator → runner → factory.
    """
    from src.agents.concurrency import PipelineSemaphore, RetryablePhaseExecutor
    from src.agents.orchestrator import PipelineOrchestrator
    from src.agents.phase_1_adapter import Phase1Adapter
    from src.agents.phase_2_adapter import Phase2Adapter
    from src.agents.phase_3_adapter import Phase3Adapter
    from src.agents.phase_4_factory import Phase4ServiceFactory
    from src.agents.runner import PipelineRunner
    from src.agents.state_persistence import SessionBoundStatePersistence
    from src.api.deps import set_phase4_factory
    from src.api.v1.pipeline import set_pipeline_runner
    from src.core.config import get_config
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.api import (
        EvidenceExtractionService,
    )
    from src.core.cross_lingual_process_and_extract_evidence.workflow import (
        TranslationService,
    )
    from src.core.ingest_and_digitize_data.document_acquisition.service import (
        DocumentAcquisitionService,
    )
    from src.core.ingest_and_digitize_data.parse_document.local.parser import (
        MinerULocalParser,
    )
    from src.core.ingest_and_digitize_data.parse_document.orchestrator import (
        DocumentParseOrchestrator,
    )
    from src.core.ingest_and_digitize_data.parse_document.remote.parser import (
        MinerURemoteParser,
    )
    from src.core.ingest_and_digitize_data.parse_document.service import (
        ParseDocumentService,
    )
    from src.core.standardize_entities_and_align_knowledge.api import (
        EntityStandardizationService,
    )

    cfg = get_config()
    session_factory = get_session_factory()

    # ── Phase 1-3 services (long-lived, no session in constructor) ──

    acquisition_service = DocumentAcquisitionService()
    remote_parser = MinerURemoteParser(api_token=cfg.mineru_api_token)
    local_parser = MinerULocalParser()
    parse_orchestrator = DocumentParseOrchestrator(remote=remote_parser, local=local_parser)
    parse_service = ParseDocumentService(parse_orchestrator)
    translation_service = TranslationService(cfg=cfg)
    extraction_service = EvidenceExtractionService(cfg=cfg)
    standardization_service = EntityStandardizationService(cfg=cfg)

    # ── Phase adapters ──

    phase_adapters = {
        "phase_1": Phase1Adapter(acquisition_service, parse_service),
        "phase_2": Phase2Adapter(translation_service, extraction_service),
        "phase_3": Phase3Adapter(standardization_service, session_factory),
    }

    # ── Orchestrator + Runner ──

    persistence = SessionBoundStatePersistence(session_factory)
    retry_executor = RetryablePhaseExecutor(max_retries=2, backoff_base=30.0)

    orchestrator = PipelineOrchestrator(
        phase_adapters=phase_adapters,
        state_persistence=persistence,
        retry_executor=retry_executor,
    )

    semaphore = PipelineSemaphore(max_concurrent=2)
    runner = PipelineRunner(
        orchestrator=orchestrator,
        semaphore=semaphore,
        state_persistence=persistence,
    )

    # ── Phase 4 factory ──

    phase4_factory = Phase4ServiceFactory(cfg=cfg)

    # ── Inject into global registries (consumed by API routes) ──

    set_pipeline_runner(runner)
    set_phase4_factory(phase4_factory)
```

> **Design note:** All imports inside `wire_dependencies()` are local (function-body) imports. This avoids the circular dependency `wiring.py → deps.py` vs `deps.py → wiring.py` at module load time. The function is only called from `lifespan` startup, by which point `deps.py` is already fully loaded.

---


After (complete file):

```python
"""FastAPI application entry point."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from src.api.v1.router import router as v1_router
from src.api.wiring import wire_dependencies, dispose_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and teardown application resources."""
    logger.info("Starting Cross Evidencebackend")
    wire_dependencies(app)
    logger.info("Pipeline orchestrator initialized")
    yield
    await dispose_engine()
    logger.info("Cross Evidencebackend stopped")


app = FastAPI(
    title="ACMG Lingua",
    description="Multi-Agent infrastructure platform for medical genetics literature automation",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(v1_router)


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}
```

Delete all imports that were moved into `wire_dependencies()` (the local imports inside the old lifespan function — `build_async_engine`, `async_session_factory`, all agent/core service imports, etc.).

---

**Step 3: Run tests**

```bash
cd backend && python -m pytest tests/ -x --tb=short 2>&1 | tail -5
```

---

**Step 4: Commit**

```bash
git add backend/src/api/wiring.py backend/app/main.py
git commit -m "refactor: extract DI composition from lifespan into wiring.wire_dependencies()"
```

---

### Task 7: Final verification + documentation

**Files:**
- Modify: `backend/progress.txt`
- Create: `backend/lesson.md` (if not present)

---

**Step 1: Run full test suite to confirm**

```bash
cd backend && python -m pytest tests/ -v --tb=short 2>&1 | tail -10
```

Confirm test count ≥ baseline.

---

**Step 2: Verify dependency direction — API layer no longer imports core service classes**

Contracts (Pydantic models / type definitions) are NOT services — API routes may import them.
Only check for service class imports:

```bash
cd backend && grep -rn "from src.core.visualize_evidence.*import.*Service\|from src.core.visualize_evidence.*import.*Linker" src/api/ && echo "VIOLATION FOUND" || echo "CLEAN"
```

Expected: `CLEAN` (contracts imports like `EvidencePatchRequest`, `ChatMessageResponse`, `DeltaEntry`, `BilingualSpan`, `TrackSpan` are allowed).

---

**Step 3: Update progress.txt**

```
[2026-06-02] Architecture cleanup: unified session factory, Phase 4 factory, removed SessionBound wrapper, merged state_persistence, extracted wiring.py [completed]
```

---

**Step 4: Record lesson.md**

```markdown
# Architecture Cleanup Lessons

## Problem
API routes (`src/api/v1/`) directly instantiated core services, bypassing the `agents` layer.
`deps.py` and `main.py` each created independent SQLAlchemy engines (dual connection pools).

## Resolution
1. Extracted engine/session_factory creation into `src/api/wiring.py` as single source of truth.
2. Created `Phase4ServiceFactory` in `src/agents/` so Phase 4 API routes delegate through agents layer.
3. Refactored `EntityStandardizationService.__init__` to not take session — session is now a method parameter.
4. Merged `state_persistence.py` and `state_persistence_factory.py` into one file with two classes.

## Prevention
- New API routes MUST NOT import from `src/core/` service modules directly.
- New service facades MUST NOT require `AsyncSession` in `__init__` — pass it as method parameter or use factory.
- All DI assembly goes in `src/api/wiring.py`, not in `app/main.py` lifespan.
```

---

**Step 5: Commit**

```bash
git add backend/progress.txt backend/lesson.md
git commit -m "docs: record architecture cleanup completion and lessons learned"
```

---

## Completion Checklist

- [ ] `deps.py` and `main.py` share the same `session_factory` (Task 1)
- [ ] `Phase4ServiceFactory` exists and is used by API routes (Tasks 2 + 3)
- [ ] `src/api/v1/*.py` contains no core service class imports (contracts/type imports allowed) (Task 3)
- [ ] `EntityStandardizationService.__init__` has no `session` parameter (Task 4)
- [ ] `session_bound_standardization.py` is deleted (Task 4)
- [ ] `state_persistence_factory.py` is deleted (Task 5)
- [ ] `state_persistence.py` contains `DirectStatePersistence` + `SessionBoundStatePersistence` (Task 5)
- [ ] `app/main.py` lifespan ≤ 15 lines (Task 6)
- [ ] `wiring.py`'s `wire_dependencies()` contains the full service graph (Task 6)
- [ ] Full test suite passes, count ≥ baseline (Task 7)
- [ ] progress.txt and lesson.md updated (Task 7)

---

## Explicitly Excluded

| Scope | Rationale |
|---|---|
| `services/model-server/` | Independent microservice, cleanly isolated |
| `frontend/` | Backend-only refactor |
| `backend/libs/` | Rust PyO3 extensions, no architectural issues |
| DAO boundary (repository migration to dao/) | P2, pure physical relocation, independent of this decoupling |
| Service facade naming standardization | P2, does not affect layering |
| Phase 4 in LangGraph | Design decision: interactive review is not suited for pipeline graph |
| `delta_audit.py:19` direct DAO model import | P2, does not violate layering but inconsistent with contracts pattern; remains after refactor |
