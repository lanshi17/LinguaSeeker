"""Tests for module initialization and factory."""
from __future__ import annotations

from unittest.mock import patch

from src.core.ingest_and_digitize_data.parse_document import (
    create_parse_service,
    ParseDocumentService,
)


def test_create_parse_service():
    """Test factory method creates service."""
    with patch("src.core.config.get_config") as mock_cfg:
        mock_cfg.return_value.parse_document.mineru_remote_api_token = "test-token"
        mock_cfg.return_value.parse_document.mineru_remote_poll_interval = 2.0
        mock_cfg.return_value.parse_document.mineru_remote_max_poll_attempts = 150
        mock_cfg.return_value.parse_document.mineru_local_model_server_url = "http://localhost:8001"
        mock_cfg.return_value.parse_document.mineru_local_model_id = "test-model"
        mock_cfg.return_value.parse_document.mineru_local_timeout = 120.0
        mock_cfg.return_value.parse_document.mineru_local_dpi = 200

        service = create_parse_service()
        assert isinstance(service, ParseDocumentService)


def test_create_parse_service_with_config():
    """Test factory method creates service with custom config."""
    from src.core.config import ParseDocumentConfig

    config = ParseDocumentConfig(
        mineru_remote_api_token="custom-token",
        mineru_local_model_server_url="http://localhost:8002",
    )

    service = create_parse_service(config=config)
    assert isinstance(service, ParseDocumentService)


def test_exports():
    """Test that all expected names are exported."""
    from src.core.ingest_and_digitize_data.parse_document import __all__

    assert "ParseDocumentService" in __all__
    assert "create_parse_service" in __all__
    assert "ParseResult" in __all__
    assert "SavedFiles" in __all__
    assert "DedupResult" in __all__
    assert "ParseAndSaveResult" in __all__
    assert "MinerUAPIError" in __all__
    assert "MinerUTimeoutError" in __all__
    assert "ParseDocumentError" in __all__
    assert "ParserExhaustedError" in __all__


def test_batch_contracts_exported():
    from src.core.ingest_and_digitize_data.parse_document import (
        MinerUBatchStatus,
        MinerULocalBatchOptions,
        MinerULocalBatchParseResult,
    )

    assert MinerUBatchStatus is not None
    assert MinerULocalBatchOptions is not None
    assert MinerULocalBatchParseResult is not None
