"""Tests for remote parser module."""

from __future__ import annotations


from src.core.ingest_and_digitize_data.parse_document.remote.parser import MinerURemoteParser


def test_mineru_remote_parser_name():
    """Test parser name property."""
    parser = MinerURemoteParser(api_token="test-token")
    assert parser.name == "mineru-remote"


def test_mineru_remote_parser_initialization():
    """Test parser initialization with config."""
    parser = MinerURemoteParser(
        api_token="test-token",
        poll_interval=3.0,
        max_poll_attempts=100,
    )
    assert parser._api_token == "test-token"
    assert parser._poll_interval == 3.0
    assert parser._max_poll_attempts == 100


def test_mineru_remote_parser_default_values():
    """Test parser default values."""
    parser = MinerURemoteParser(api_token="test-token")
    assert parser._poll_interval == 2.0
    assert parser._max_poll_attempts == 150
