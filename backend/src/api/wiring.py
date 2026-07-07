"""Application dependency wiring — single source of truth for engine & session factory."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from redis.asyncio import Redis as AsyncRedis

from src.core.config import get_config
from src.dao.postgresql.connection import async_session_factory, build_async_engine
from src.dao.postgresql.job_queue import JobQueueRepository
from src.dao.redis.connection import build_redis_client

if TYPE_CHECKING:
    from src.agents.dispatcher import SingleJobDispatcher
    from src.core.ingest_and_digitize_data.parse_document.local.parser import (
        MinerULocalParser,
    )

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_redis_client: AsyncRedis | None = None
_local_parser: MinerULocalParser | None = None
_dispatcher: SingleJobDispatcher | None = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the singleton session factory (set by wire_dependencies)."""
    if _session_factory is None:
        raise RuntimeError("Session factory not initialized — call wire_dependencies() first")
    return _session_factory


def get_engine() -> AsyncEngine | None:
    """Return the singleton engine (or None if not yet initialized).

    Prefer ``get_session_factory()`` for normal DB access; this accessor
    exists for health-check and shutdown paths that need the raw engine.
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
        await _redis_client.close()
        _redis_client = None


def get_local_parser() -> MinerULocalParser | None:
    """Return the singleton MinerU local parser (or None if not yet initialized)."""
    return _local_parser


def get_dispatcher() -> SingleJobDispatcher | None:
    """Return the singleton job dispatcher (or None if not yet initialized)."""
    return _dispatcher


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
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.api import (
        EvidenceExtractionService,
    )
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.field_profile import (
        ExtractionProfile,
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

    global _engine, _session_factory, _redis_client, _local_parser, _dispatcher

    cfg = get_config()

    # ── PostgreSQL engine/session singleton ──────────────────────────
    if _engine is None:
        _engine = build_async_engine(cfg)
    if _session_factory is None:
        _session_factory = async_session_factory(_engine)

    # ── Redis client singleton ───────────────────────────────────────
    _redis_client = build_redis_client(cfg)

    # ── Document processing cache (L1 Redis + L2 PostgreSQL) ──────────
    from src.agents.processing_cache import DocumentProcessingCacheService

    processing_cache = DocumentProcessingCacheService(
        redis_client=_redis_client,
        session_factory=get_session_factory(),
    )

    session_factory = get_session_factory()

    # ── Phase 1-3 services (long-lived, no session in constructor) ──

    acquisition_service = DocumentAcquisitionService()
    pd_cfg = cfg.parse_document
    remote_parser = MinerURemoteParser(
        api_token=cfg.mineru_api_token,
        poll_interval=pd_cfg.mineru_remote_poll_interval,
        max_poll_attempts=pd_cfg.mineru_remote_max_poll_attempts,
    )
    _local_parser = MinerULocalParser(
        parse_url=pd_cfg.mineru_local_parse_url,
        model_id=pd_cfg.mineru_local_model_id,
        timeout=pd_cfg.mineru_local_timeout,
        dpi=pd_cfg.mineru_local_dpi,
        api_key=cfg.inference_api_key,
    )
    parse_orchestrator = DocumentParseOrchestrator(remote=remote_parser, local=_local_parser)
    parse_service = ParseDocumentService(parse_orchestrator)
    translation_service = TranslationService(cfg=cfg)
    extraction_service = EvidenceExtractionService(
        cfg=cfg,
        extraction_profile=ExtractionProfile.NONE,
    )
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
        processing_cache=processing_cache,
        processing_cache_enabled=cfg.pipeline.cache_enabled,
        duplicate_run_prevention_enabled=cfg.pipeline.dedup_enabled,
    )
    # Let the orchestrator push intermediate state updates to the runner's
    # in-memory cache so the status endpoint reflects phase progress in
    # real time (not just after the entire pipeline completes).
    orchestrator.on_state_change = runner.remember_state

    # ── Phase 4 factory ──

    phase4_factory = Phase4ServiceFactory(cfg=cfg, session_factory=session_factory)

    # ── Job queue + dispatcher ──

    from src.agents.dispatcher import SingleJobDispatcher
    from src.api.v1.pipeline import set_job_queue

    job_queue = JobQueueRepository(session_factory)
    _dispatcher = SingleJobDispatcher(
        runner=runner,
        job_queue=job_queue,
        poll_interval=2.0,
    )

    # ── Inject into global registries (consumed by API routes) ──

    set_pipeline_runner(runner)
    set_phase4_factory(phase4_factory)
    set_job_queue(job_queue)
