"""Tests for wiring config propagation to parsers."""
from __future__ import annotations

from contextlib import ExitStack
from unittest.mock import MagicMock, patch

from src.core.config import ParseDocumentConfig

# Source module paths for classes imported inside wire_dependencies()
_REMOTE_PARSER_MOD = "src.core.ingest_and_digitize_data.parse_document.remote.parser.MinerURemoteParser"
_LOCAL_PARSER_MOD = "src.core.ingest_and_digitize_data.parse_document.local.parser.MinerULocalParser"


def _patch_wire_deps(stack: ExitStack):
    """Patch all dependencies wired inside wire_dependencies()."""
    for mod_path in [
        "src.core.ingest_and_digitize_data.document_acquisition.service.DocumentAcquisitionService",
        "src.core.ingest_and_digitize_data.parse_document.orchestrator.DocumentParseOrchestrator",
        "src.core.ingest_and_digitize_data.parse_document.service.ParseDocumentService",
        "src.core.cross_lingual_process_and_extract_evidence.workflow.TranslationService",
        "src.core.cross_lingual_process_and_extract_evidence.extract_evidence.api.EvidenceExtractionService",
        "src.core.standardize_entities_and_align_knowledge.api.EntityStandardizationService",
        "src.agents.orchestrator.PipelineOrchestrator",
        "src.agents.concurrency.PipelineSemaphore",
        "src.agents.concurrency.RetryablePhaseExecutor",
        "src.agents.runner.PipelineRunner",
        "src.agents.state_persistence.SessionBoundStatePersistence",
        "src.agents.phase_1_adapter.Phase1Adapter",
        "src.agents.phase_2_adapter.Phase2Adapter",
        "src.agents.phase_3_adapter.Phase3Adapter",
        "src.agents.phase_4_factory.Phase4ServiceFactory",
        "src.api.v1.pipeline.set_pipeline_runner",
        "src.api.deps.set_phase4_factory",
        "src.api.wiring.get_session_factory",
        "src.api.wiring.build_redis_client",
    ]:
        stack.enter_context(patch(mod_path))


def test_remote_parser_receives_all_config():
    """MinerURemoteParser should receive poll_interval and max_poll_attempts."""
    from src.core.config import get_config
    get_config.cache_clear()

    pd = ParseDocumentConfig(
        mineru_remote_poll_interval=3.0,
        mineru_remote_max_poll_attempts=200,
        mineru_local_api_url="http://localhost:8000",
        mineru_local_timeout=600.0,
        mineru_local_backend="vlm",
    )

    with ExitStack() as stack:
        _patch_wire_deps(stack)
        mock_remote = stack.enter_context(patch(_REMOTE_PARSER_MOD))
        stack.enter_context(patch(_LOCAL_PARSER_MOD))
        mock_cfg = stack.enter_context(patch("src.core.config.get_config"))

        cfg = MagicMock()
        cfg.parse_document = pd
        cfg.mineru_api_token = "test-token"
        mock_cfg.return_value = cfg

        from src.api.wiring import wire_dependencies
        wire_dependencies()

        _, kwargs = mock_remote.call_args
        assert kwargs.get("api_token") == "test-token"
        assert kwargs.get("poll_interval") == 3.0
        assert kwargs.get("max_poll_attempts") == 200


def test_local_parser_receives_all_config():
    """MinerULocalParser should receive api_url, timeout, backend."""
    from src.core.config import get_config
    get_config.cache_clear()

    pd = ParseDocumentConfig(
        mineru_remote_poll_interval=2.0,
        mineru_remote_max_poll_attempts=150,
        mineru_local_api_url="http://mineru:30000",
        mineru_local_timeout=300.0,
        mineru_local_backend="pipeline",
    )

    with ExitStack() as stack:
        _patch_wire_deps(stack)
        stack.enter_context(patch(_REMOTE_PARSER_MOD))
        mock_local = stack.enter_context(patch(_LOCAL_PARSER_MOD))
        mock_cfg = stack.enter_context(patch("src.core.config.get_config"))

        cfg = MagicMock()
        cfg.parse_document = pd
        cfg.mineru_api_token = ""
        mock_cfg.return_value = cfg

        from src.api.wiring import wire_dependencies
        wire_dependencies()

        _, kwargs = mock_local.call_args
        assert kwargs.get("api_url") == "http://mineru:30000"
        assert kwargs.get("timeout") == 300.0
        assert kwargs.get("backend") == "pipeline"
