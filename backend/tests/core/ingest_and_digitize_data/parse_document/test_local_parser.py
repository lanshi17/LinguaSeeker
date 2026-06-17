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
        model_server_url="http://localhost:8002",
        model_id="test-model",
        timeout=60.0,
        dpi=150,
    )
    assert parser._base_url == "http://localhost:8002"
    assert parser._model_id == "test-model"
    assert parser._timeout == 60.0
    assert parser._dpi == 150


def test_mineru_local_parser_default_values():
    """Test parser default values."""
    parser = MinerULocalParser()
    assert parser._base_url == "http://localhost:8001"
    assert parser._model_id == "opendatalab/MinerU2.5-Pro-2604-1.2B"
    assert parser._timeout == 120.0
    assert parser._dpi == 200
