# Backend Architecture Cleanup: api→agents→core→dao 分层强化

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 消除 API 层对 core 层的直接依赖，补齐 Phase 4 的 agents 层，统一会话工厂/引擎，合并冗余模块，清理变通代码。

**Architecture:** 严格遵守 `api → agents → core → dao` 单向依赖。API 路由只做 HTTP 关注点（参数解析、状态码、响应模型），通过 agents 层的 factory/adapter 委托到 core 服务。Phase 1-3 保持 LangGraph pipeline 模式；Phase 4 使用 thin factory delegate 模式（不在 graph 内）。所有 services 的长生命周期依赖（cfg, LLM client）在 wiring 层注入，短生命周期依赖（AsyncSession）通过 factory 创建或方法参数传入。

**Tech Stack:** FastAPI + Pydantic + SQLAlchemy async + LangGraph

---

## 设计决策速查

| 决策 | 结论 | 理由 |
|---|---|---|
| 重构范围 | `backend/src/` + `backend/app/` | model-server 独立微服务，不动；前端不动；libs 不动 |
| Phase 4 agents 模式 | thin factory delegate | Phase 4 是交互式 request-response，不适合 LangGraph node |
| Phase 4 服务生命周期 | per-request，通过 factory 创建 | 服务构造函数需要 AsyncSession |
| app/main.py DI | 抽取到 `src/api/wiring.py` | lifespan 只管生命周期事件 |
| state_persistence | 合并为一个文件，两个 class | `DirectStatePersistence`(测试) + `SessionBoundStatePersistence`(生产) |
| SessionBoundStandardizationService | 消除，改为方法参数传 session | 根本解法，不是包 wrapper |
| DAO 边界 | 本次不动 (P2) | 纯物理位移，无解耦收益 |
| 测试策略 | 可跟着改，覆盖率不降 | import 路径和 mock 目标会变 |

---

## 现状问题清单

```
A. API 层直接实例化 core 服务 ← P0
   src/api/v1/evidence.py:29 → FeedbackService(session)
   src/api/v1/chat.py:43 → ChatService(session)
   src/api/v1/delta_audit.py:32 → DeltaAuditService()
   src/api/v1/source_link.py:27 → SourceLinker(session)

B. Phase 4 没有 agents 层 ← P0
   src/agents/ 只有 phase_1/2/3_adapter.py

C. deps.py 和 main.py 各自创建独立 engine ← P0 (新增)
   deps.py:15-21 → _get_session_factory() 懒加载创建 engine (实际 engine 创建在 line 19)
   main.py:58-59 → lifespan 里 build_async_engine(cfg) + async_session_factory(engine)
   结果: 两个连接池，两套事务隔离

D. EntityStandardizationService 构造函数绑 session ← P1
   src/core/standardize_entities_and_align_knowledge/api.py:102
   → def __init__(self, cfg, session) 迫使引入 SessionBoundStandardizationService wrapper

E. state_persistence 两个文件做同一件事 ← P1
   state_persistence.py → DirectStatePersistence(session) 测试用
   state_persistence_factory.py → SessionBoundPersistence(session_factory) 生产用

F. app/main.py lifespan ~100 行 DI 逻辑 ← P1
   应该抽到独立模块

G. DAO 边界模糊 ← P2 (本次不动)
   标准化 repositories 在 core/ 而非 dao/

H. 服务 facade 命名不统一 ← P2 (本次不动)
   api.py / service.py / workflow.py 混用

I. delta_audit.py 直接 import DAO model ← P2 (本次不动，已记录)
   src/api/v1/delta_audit.py:19 → from src.dao.models import ReviewAuditEvent
   用于 _to_response() 的 ORM→API 转换。不违反 api→dao 分层，
   但和 contracts 模式不一致（应该用 contracts 类型而非暴露 ORM model）。
```

---

### Task 0: 准备 — 确认当前测试基线

**目的:** 记录重构前的测试通过数，确保重构后不降。

**Step 1: 运行全量后端测试**

Run:
```bash
cd backend && python -m pytest tests/ -x --tb=short 2>&1 | tail -20
```

**Step 2: 记录基线**

将通过的测试总数记到 `progress.txt`：
```
[2026-06-02] Architecture cleanup baseline: NNN tests passed [baseline]
```

---

### Task 1: 统一会话工厂 — 消除 deps.py 和 main.py 的双 engine

**Files:**
- Modify: `backend/src/api/deps.py:1-28`
- Modify: `backend/app/main.py:22-100`
- Create: `backend/src/api/wiring.py`

**Why first:** 这是后续所有改动的依赖 — Phase 4 factory 和 Phase 3 adapter 都需要同一个 session_factory。先统一工厂，再建上层。

---

**Step 1: 创建 `src/api/wiring.py` — 提取 engine/session_factory 创建逻辑**

```python
"""Application dependency wiring — single source of truth for engine & session factory."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.core.config import get_config
from src.dao.connection import async_session_factory, build_async_engine

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

**Step 2: 改 `src/api/deps.py` — 委托给 wiring.py**

将 `deps.py` 中的 `_engine`、`_session_factory`、`_get_session_factory` 和 `build_async_engine` import 全部删掉，改为从 wiring 导入：

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

**Step 3: 改 `app/main.py` lifespan — 使用 wiring 的 engine**

将 lifespan 中的：
```python
cfg = get_config()
engine = build_async_engine(cfg)
session_factory = async_session_factory(engine)
```
替换为：
```python
from src.api.wiring import get_session_factory, dispose_engine
session_factory = get_session_factory()
```

Teardown 中的 `await engine.dispose()` 替换为 `await dispose_engine()`。

---

**Step 4: 运行测试验证**

```bash
cd backend && python -m pytest tests/ -x --tb=short 2>&1 | tail -5
```

Expected: 测试数不变（和基线一致）。

**Step 5: 提交**

```bash
git add backend/src/api/wiring.py backend/src/api/deps.py backend/app/main.py
git commit -m "refactor: unify session factory into wiring.py, eliminate dual engine"
```

---

### Task 2: 创建 Phase 4 agents 层 factory

**Files:**
- Create: `backend/src/agents/phase_4_factory.py`

**目的:** API 层不再直接 `import` core 服务。所有 Phase 4 服务通过 factory 创建。

---

**Step 1: 创建 `src/agents/phase_4_factory.py`**

```python
"""Phase 4 service factory — thin delegate between API and core services.

Phase 4 (evidence review, chat, audit, source linking) is interactive
request-response, not a LangGraph pipeline node.  This factory provides
the agents-layer boundary so API routes never import core services directly.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.visualize_evidence_with_expert_in_loop.chat_service import ChatService
from src.core.visualize_evidence_with_expert_in_loop.delta_audit_service import DeltaAuditService
from src.core.visualize_evidence_with_expert_in_loop.feedback_service import FeedbackService
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

**Step 2: 运行测试验证模块可导入**

```bash
cd backend && python -c "from src.agents.phase_4_factory import Phase4ServiceFactory; print('OK')"
```

Expected: `OK`

**Step 3: 提交**

```bash
git add backend/src/agents/phase_4_factory.py
git commit -m "feat: add Phase4ServiceFactory as agents-layer boundary for Phase 4"
```

---

### Task 3: API 层改造 — Phase 4 路由通过 factory 委托

**Files:**
- Modify: `backend/src/api/v1/evidence.py`
- Modify: `backend/src/api/v1/chat.py`
- Modify: `backend/src/api/v1/delta_audit.py`
- Modify: `backend/src/api/v1/source_link.py`
- Modify: `backend/src/api/deps.py` (加 factory 依赖注入)
- Modify: `backend/app/main.py` (创建 factory 并注入)

---

**Step 1: 在 `deps.py` 添加 `get_phase4_factory` 依赖**

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

**Step 2: 改 `src/api/v1/evidence.py` — 用 factory 替代直接实例化**

Before:
```python
from src.core.visualize_evidence_with_expert_in_loop.feedback_service import (
    FeedbackService,
    PatchResult,
)
...
service = FeedbackService(session)
```

After:
```python
from src.api.deps import get_db_session, get_phase4_factory
...
factory = get_phase4_factory()
service = factory.create_feedback_service(session)
```

`PatchResult` 的 import 保留（它是 dataclass，不是服务）。

---

**Step 3: 改 `src/api/v1/chat.py` — 用 factory**

Before:
```python
from src.core.visualize_evidence_with_expert_in_loop.chat_service import (
    ChatService,
)
...
service = ChatService(session)
```

After:
```python
from src.api.deps import get_db_session, get_phase4_factory
...
factory = get_phase4_factory()
service = factory.create_chat_service(session)
```

---

**Step 4: 改 `src/api/v1/delta_audit.py` — 用 factory**

Before:
```python
from src.core.visualize_evidence_with_expert_in_loop.delta_audit_service import (
    DeltaAuditService,
)
...
service = DeltaAuditService()
```

After:
```python
from src.api.deps import get_phase4_factory
...
service = get_phase4_factory().delta_audit
```

---

**Step 5: 改 `src/api/v1/source_link.py` — 用 factory**

Before:
```python
from src.core.visualize_evidence_with_expert_in_loop.source_linker import (
    SourceLinker,
)
...
linker = SourceLinker(session)
```

After:
```python
from src.api.deps import get_db_session, get_phase4_factory
...
factory = get_phase4_factory()
linker = factory.create_source_linker(session)
```

---

**Step 6: 在 `app/main.py` lifespan 创建并注入 factory**

```python
from src.agents.phase_4_factory import Phase4ServiceFactory
from src.api.deps import set_phase4_factory

# 在 lifespan startup 中，set_pipeline_runner 附近：
phase4_factory = Phase4ServiceFactory(cfg=cfg)
set_phase4_factory(phase4_factory)
```

---

**Step 7: 运行测试**

```bash
cd backend && python -m pytest tests/ -x --tb=short 2>&1 | tail -5
```

Expected: 测试数较基线不变（只有 API 路由 import 路径变了，无行为变化）。

**Step 8: 提交**

```bash
git add backend/src/api/v1/evidence.py backend/src/api/v1/chat.py \
        backend/src/api/v1/delta_audit.py backend/src/api/v1/source_link.py \
        backend/src/api/deps.py backend/app/main.py
git commit -m "refactor: Phase 4 API routes delegate through Phase4ServiceFactory"
```

---

### Task 4: 重构 EntityStandardizationService — 消除 SessionBound wrapper

**Files:**
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/api.py`
- Modify: `backend/src/agents/phase_3_adapter.py`
- Delete: `backend/src/agents/session_bound_standardization.py`
- Modify: `backend/app/main.py`

---

**Step 1: 改 `EntityStandardizationService.__init__` — 去掉 session 参数**

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

**Step 2: 改 `run_dual_result` 签名 — session 作为方法参数**

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

注意：内部所有 `self._session` 引用改为局部变量 `session`。重点——`SimilarityTerminologyMatcher` 的构造也引用了 `self._session`，必须同步改：

```python
# api.py ~line 126 — PgvectorTerminologyRepository 也绑了 self._session
similarity_matcher = SimilarityTerminologyMatcher(
    ...
    repository=PgvectorTerminologyRepository(session),  # ← self._session → session
    ...
)
```

完整变更：`StandardizationRepository(self._session)` → `StandardizationRepository(session)`，`PgvectorTerminologyRepository(self._session)` → `PgvectorTerminologyRepository(session)`。

---

**Step 3: 改 `Phase3Adapter` — 持有 service + session_factory，自己管理 session**

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

**Step 4: 删除 `session_bound_standardization.py`**

```bash
rm backend/src/agents/session_bound_standardization.py
```

---

**Step 5: 改 `app/main.py` lifespan — Phase3Adapter 构造方式**

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

**Step 6: 更新 `Phase3Adapter` 测试**

`tests/agents/test_phase_3_adapter.py` 实际从未 import `SessionBoundStandardizationService`，测试直接用 `MagicMock()` 构造 mock 对象。需要改的是：

1. `Phase3Adapter` 签名变了（多了一个 `session_factory` 参数），构造时传入 `mock_session_factory = MagicMock()`
2. `mock_standardization.run_dual_result` 签名变了（多了 `session` 作为第一个位置参数），更新 `AsyncMock` 的断言，确认调用时传入了 session

改动量很小——本质上是加一个 mock 参数 + 调整一个方法签名的断言。

---

**Step 7: 运行测试**

```bash
cd backend && python -m pytest tests/ -x --tb=short 2>&1 | tail -5
```

---

**Step 8: 提交**

```bash
git add backend/src/core/standardize_entities_and_align_knowledge/api.py \
        backend/src/agents/phase_3_adapter.py \
        backend/app/main.py \
        tests/agents/test_phase_3_adapter.py
git rm backend/src/agents/session_bound_standardization.py
git commit -m "refactor: pass session as method param to EntityStandardizationService, remove SessionBound wrapper"
```

---

### Task 5: 合并 state_persistence 两个文件

**Files:**
- Modify: `backend/src/agents/state_persistence.py` (合并两个 class 进来)
- Delete: `backend/src/agents/state_persistence_factory.py`
- Modify: `backend/src/agents/orchestrator.py` (更新 import)
- Modify: `backend/src/agents/runner.py` (更新 import)
- Modify: `backend/app/main.py` (更新 import)
- Modify: `backend/tests/agents/test_state_persistence.py` (更新 import)
- Modify: `backend/tests/agents/test_state_persistence_layer.py` (更新 import)

---

**Step 1: 合并 — 在 `state_persistence.py` 中加 `SessionBoundStatePersistence`**

保留原有 `StatePersistenceService`（重命名为 `DirectStatePersistence`），追加 `SessionBoundStatePersistence`：

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
from src.dao.models import PipelineRunState


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

**Step 2: 更新所有 import — orchestrator, runner, main, tests**

由于 `StatePersistenceService` alias 已删除，所有消费者改为导入具体类：

- `orchestrator.py`: 
  - 删除 `from src.agents.state_persistence import StatePersistenceService`
  - 改为 `from src.agents.state_persistence import SessionBoundStatePersistence`
  - `__init__` 类型标注从 `StatePersistenceService` 改为 `SessionBoundStatePersistence`
- `runner.py`: 
  - 同上，类型标注改为 `SessionBoundStatePersistence`
- `app/main.py`: `from src.agents.state_persistence import SessionBoundStatePersistence`
- `tests/agents/test_state_persistence.py`: `from src.agents.state_persistence import DirectStatePersistence`
- `tests/agents/test_state_persistence_layer.py`: 同上

---

**Step 3: 删除 `state_persistence_factory.py`**

```bash
rm backend/src/agents/state_persistence_factory.py
```

---

**Step 4: 运行测试**

```bash
cd backend && python -m pytest tests/agents/test_state_persistence*.py -x --tb=short
```

---

**Step 5: 提交**

```bash
git add backend/src/agents/state_persistence.py \
        backend/src/agents/orchestrator.py \
        backend/src/agents/runner.py \
        backend/app/main.py \
        tests/agents/test_state_persistence.py \
        tests/agents/test_state_persistence_layer.py
git rm backend/src/agents/state_persistence_factory.py
git commit -m "refactor: merge state_persistence_factory into state_persistence as SessionBoundStatePersistence"
```

---

### Task 6: 抽取 app/main.py lifespan DI 到 wiring.py

**Files:**
- Modify: `backend/src/api/wiring.py` (追加 `wire_dependencies` 函数)
- Modify: `backend/app/main.py` (lifespan 缩到 ~10 行)

---

**Step 1: 在 `wiring.py` 追加 `wire_dependencies(app)` 函数**

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

---

**Step 2: 精简 `app/main.py` lifespan**

After:
```python
from src.api.wiring import wire_dependencies, dispose_engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and teardown application resources."""
    logger.info("Starting ACMG Lingua backend")
    wire_dependencies(app)
    logger.info("Pipeline orchestrator initialized")
    yield
    await dispose_engine()
    logger.info("ACMG Lingua backend stopped")
```

删除 lifespan 中所有被移走的 import。

---

**Step 3: 运行测试**

```bash
cd backend && python -m pytest tests/ -x --tb=short 2>&1 | tail -5
```

---

**Step 4: 提交**

```bash
git add backend/src/api/wiring.py backend/app/main.py
git commit -m "refactor: extract DI composition from lifespan into wiring.wire_dependencies()"
```

---

### Task 7: 最终验证 + 文档

**Files:**
- Modify: `backend/progress.txt`
- Create: `backend/lesson.md` (如不存在)

---

**Step 1: 运行全量测试确认**

```bash
cd backend && python -m pytest tests/ -v --tb=short 2>&1 | tail -10
```

确认测试数 ≥ 基线。

---

**Step 2: 验证依赖方向 — API 层不再直接 import core 服务类**

contracts（Pydantic 模型/类型定义）不算服务——API 路由可以 import 它们。
只检查服务类 import：

```bash
cd backend && grep -rn "from src.core.visualize_evidence.*import.*Service\|from src.core.visualize_evidence.*import.*Linker" src/api/ && echo "VIOLATION FOUND" || echo "CLEAN"
```

Expected: `CLEAN` (contracts imports like `EvidencePatchRequest`, `ChatMessageResponse`, `DeltaEntry`, `BilingualSpan`, `TrackSpan` 是允许的)

---

**Step 3: 更新 progress.txt**

```
[2026-06-02] Architecture cleanup: unified session factory, Phase 4 factory, removed SessionBound wrapper, merged state_persistence, extracted wiring.py [completed]
```

---

**Step 4: 记录 lesson.md**

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
- New API routes MUST NOT import from `src/core/` directly.
- New service facades MUST NOT require `AsyncSession` in `__init__` — pass it as method parameter or use factory.
- All DI assembly goes in `src/api/wiring.py`, not in `app/main.py` lifespan.
```

---

**Step 5: 提交**

```bash
git add backend/progress.txt backend/lesson.md
git commit -m "docs: record architecture cleanup completion and lessons learned"
```

---

## 完成检查清单

- [ ] `deps.py` 和 `main.py` 共享同一个 session_factory（Task 1）
- [ ] `Phase4ServiceFactory` 存在且被 API 路由使用（Task 2 + 3）
- [ ] `src/api/v1/*.py` 不含 core 服务类 import（contracts/类型 import 允许）（Task 3）
- [ ] `EntityStandardizationService.__init__` 无 session 参数（Task 4）
- [ ] `session_bound_standardization.py` 已删除（Task 4）
- [ ] `state_persistence_factory.py` 已删除（Task 5）
- [ ] `state_persistence.py` 包含 `DirectStatePersistence` + `SessionBoundStatePersistence`（Task 5）
- [ ] `app/main.py` lifespan ≤ 15 行（Task 6）
- [ ] `wiring.py` 的 `wire_dependencies()` 包含完整服务图（Task 6）
- [ ] 全量测试通过，数量 ≥ 基线（Task 7）
- [ ] progress.txt 和 lesson.md 已更新（Task 7）

---

## 不改的（明确排除）

| 范围 | 理由 |
|---|---|
| `services/model-server/` | 独立微服务，隔离干净 |
| `frontend/` | 本次只做后端 |
| `backend/libs/` | Rust PyO3 扩展，无架构问题 |
| DAO 边界（repository 迁移到 dao/） | P2，纯物理位移，和本次解耦独立 |
| 服务 facade 命名统一 | P2，不影响分层 |
| Phase 4 纳入 LangGraph | 设计决定：交互式审查不适合 pipeline graph |
| `delta_audit.py:19` 直接 import DAO model | P2，不违反分层但和 contracts 模式不一致，改后仍然存在 |
