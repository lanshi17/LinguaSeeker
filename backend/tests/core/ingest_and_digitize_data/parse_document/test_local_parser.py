"""Tests for local parser module."""
from __future__ import annotations

from src.core.ingest_and_digitize_data.parse_document.local.parser import MinerULocalParser


def test_mineru_local_parser_name():
    """Test parser name property."""
    parser = MinerULocalParser()
    assert parser.name == "mineru-local"


def test_mineru_local_parser_initialization():
    """Test parser initialization with config."""
    parser = MinerULocalParser(
        api_url="http://mineru:30000",
        timeout=300.0,
        backend="pipeline",
    )
    assert parser._api_url == "http://mineru:30000"
    assert parser._timeout == 300.0
    assert parser._backend == "pipeline"


def test_mineru_local_parser_default_values():
    """Test parser default values."""
    parser = MinerULocalParser()
    assert parser._api_url == "http://localhost:8001"
    assert parser._timeout == 600.0
    assert parser._backend == "vlm"
