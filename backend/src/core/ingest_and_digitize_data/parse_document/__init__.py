"""Document parsing module — MinerU VLM engine."""

from .contracts import (
    DedupResult,
    DocumentMetadata,
    FigurePosition,
    PageContent,
    ParseAndSaveResult,
    ParseResult,
    SavedFiles,
    TableStructure,
)
from .exceptions import (
    MinerUAPIError,
    MinerUTimeoutError,
    ParseDocumentError,
    ParserExhaustedError,
)
from .service import ParseDocumentService


def create_parse_service(config=None) -> ParseDocumentService:
    """Create a ParseDocumentService instance.

    Args:
        config: Optional ParseDocumentConfig. If None, loads from global config.

    Returns:
        Configured ParseDocumentService instance.
    """
    from src.core.config import ParseDocumentConfig, get_config

    from .local.parser import MinerULocalParser
    from .orchestrator import DocumentParseOrchestrator
    from .remote.parser import MinerURemoteParser

    if config is None:
        cfg = get_config()
        config = cfg.parse_document

    remote = MinerURemoteParser(
        api_token=config.mineru_remote_api_token,
        poll_interval=config.mineru_remote_poll_interval,
        max_poll_attempts=config.mineru_remote_max_poll_attempts,
    )

    local = MinerULocalParser(
        model_server_url=config.mineru_local_model_server_url,
        model_id=config.mineru_local_model_id,
        timeout=config.mineru_local_timeout,
        dpi=config.mineru_local_dpi,
    )

    orchestrator = DocumentParseOrchestrator(remote=remote, local=local)
    return ParseDocumentService(orchestrator=orchestrator)


__all__ = [
    "DedupResult",
    "DocumentMetadata",
    "FigurePosition",
    "MinerUAPIError",
    "MinerUTimeoutError",
    "PageContent",
    "ParseAndSaveResult",
    "ParseDocumentError",
    "ParseDocumentService",
    "ParseResult",
    "ParserExhaustedError",
    "SavedFiles",
    "TableStructure",
    "create_parse_service",
]
