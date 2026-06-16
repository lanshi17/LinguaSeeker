"""Application dependency wiring — single source of truth for engine & session factory."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from redis.asyncio import Redis as AsyncRedis

from src.core.config import get_config
from src.dao.postgresql.connection import async_session_factory, build_async_engine
from src.dao.redis.connection import build_redis_client

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_redis_client: AsyncRedis | None = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Lazy-init and return the singleton session factory."""
    global _engine, _session_factory
    if _session_factory is None:
        _engine = build_async_engine(get_config())
        _session_factory = async_session_factory(_engine)
    return _session_factory


def get_engine() -> AsyncEngine | None:
    """Return the singleton engine (or None if not yet initialized).

    Used by health checks to verify DB connectivity without creating
    a second engine.
    """
    return _engine


async def dispose_engine() -> None:
    """Teardown the engine (called from lifespan shutdown)."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None


def get_redis_client() -> AsyncRedis | None:
    """Return the singleton async Redis client (or None if not yet initialized)."""
    return _redis_client


async def dispose_redis() -> None:
    """Teardown the Redis client (called from lifespan shutdown)."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None


def wire_dependencies() -> None:
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

    # ── Redis client singleton ───────────────────────────────────────
    global _redis_client
    _redis_client = build_redis_client(cfg)

    session_factory = get_session_factory()

    # ── Phase 1-3 services (long-lived, no session in constructor) ──

    acquisition_service = DocumentAcquisitionService()
    pd_cfg = cfg.parse_document
    remote_parser = MinerURemoteParser(
        api_token=cfg.mineru_api_token,
        poll_interval=pd_cfg.mineru_remote_poll_interval,
        max_poll_attempts=pd_cfg.mineru_remote_max_poll_attempts,
    )
    local_parser = MinerULocalParser(
        api_url=pd_cfg.mineru_local_api_url,
        timeout=pd_cfg.mineru_local_timeout,
        backend=pd_cfg.mineru_local_backend,
    )
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
    # Let the orchestrator push intermediate state updates to the runner's
    # in-memory cache so the status endpoint reflects phase progress in
    # real time (not just after the entire pipeline completes).
    orchestrator.on_state_change = runner.remember_state

    # ── Phase 4 factory ──

    phase4_factory = Phase4ServiceFactory(cfg=cfg)

    # ── Inject into global registries (consumed by API routes) ──

    set_pipeline_runner(runner)
    set_phase4_factory(phase4_factory)
