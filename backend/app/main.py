"""FastAPI application entry point."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from src.api.v1.router import router as v1_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and teardown application resources."""
    logger.info("Starting ACMG Lingua backend")

    # Initialize pipeline orchestrator
    from src.core.config import get_config
    from src.dao.connection import (
        async_session_factory,
        build_async_engine,
    )
    from src.agents.concurrency import PipelineSemaphore, RetryablePhaseExecutor
    from src.agents.orchestrator import PipelineOrchestrator
    from src.agents.runner import PipelineRunner
    from src.agents.phase_1_adapter import Phase1Adapter
    from src.agents.phase_2_adapter import Phase2Adapter
    from src.agents.phase_3_adapter import Phase3Adapter
    from src.agents.state_persistence_factory import SessionBoundPersistence
    from src.core.ingest_and_digitize_data.document_acquisition.service import (
        DocumentAcquisitionService,
    )
    from src.core.ingest_and_digitize_data.parse_document.service import (
        ParseDocumentService,
    )
    # C2 fix: Use DocumentParseOrchestrator with remote + local parsers
    from src.core.ingest_and_digitize_data.parse_document.orchestrator import (
        DocumentParseOrchestrator,
    )
    from src.core.ingest_and_digitize_data.parse_document.remote.parser import (
        MinerURemoteParser,
    )
    from src.core.ingest_and_digitize_data.parse_document.local.parser import (
        MinerULocalParser,
    )
    from src.core.cross_lingual_process_and_extract_evidence.workflow import (
        TranslationService,
    )
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.api import (
        EvidenceExtractionService,
    )
    from src.agents.session_bound_standardization import (
        SessionBoundStandardizationService,
    )
    from src.api.v1.pipeline import set_pipeline_runner

    cfg = get_config()
    engine = build_async_engine(cfg)
    session_factory = async_session_factory(engine)

    # Build phase adapters with long-lived services
    acquisition_service = DocumentAcquisitionService()
    remote_parser = MinerURemoteParser(api_token=cfg.mineru_api_token)
    local_parser = MinerULocalParser()
    parse_orchestrator = DocumentParseOrchestrator(
        remote=remote_parser,
        local=local_parser,
    )
    parse_service = ParseDocumentService(parse_orchestrator)
    translation_service = TranslationService(cfg=cfg)
    extraction_service = EvidenceExtractionService(cfg=cfg)

    # Session-bound persistence for orchestrator and runner
    session_persistence = SessionBoundPersistence(session_factory=session_factory)

    # EntityStandardizationService needs a session — use session-per-request
    standardization_service = SessionBoundStandardizationService(
        cfg=cfg,
        session_factory=session_factory,
    )

    phase_adapters = {
        "phase_1": Phase1Adapter(acquisition_service, parse_service),
        "phase_2": Phase2Adapter(translation_service, extraction_service),
        "phase_3": Phase3Adapter(standardization_service),
    }

    retry_executor = RetryablePhaseExecutor(max_retries=2, backoff_base=30.0)

    orchestrator = PipelineOrchestrator(
        phase_adapters=phase_adapters,
        state_persistence=session_persistence,
        retry_executor=retry_executor,
    )

    semaphore = PipelineSemaphore(max_concurrent=2)
    runner = PipelineRunner(
        orchestrator=orchestrator,
        semaphore=semaphore,
        state_persistence=session_persistence,
    )

    set_pipeline_runner(runner)
    logger.info("Pipeline orchestrator initialized")

    yield

    # Teardown
    await engine.dispose()
    logger.info("ACMG Lingua backend stopped")


app = FastAPI(
    title="ACMG Lingua Backend",
    description="Multi-Agent infrastructure for medical genetics literature automation",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(v1_router)


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}
