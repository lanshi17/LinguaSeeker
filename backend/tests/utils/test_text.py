"""Tests for utils/text.py."""
from __future__ import annotations

from src.utils.text import sanitize_filename


class TestSanitizeFilename:
    def test_basic_sanitize(self):
        assert sanitize_filename('test: file? name') == 'test_ file_ name'

    def test_empty_string(self):
        assert sanitize_filename("") == "paper"

    def test_none_value(self):
        assert sanitize_filename(None) == "paper"

    def test_only_invalid_chars(self):
        assert sanitize_filename(':::') == '_'

    def test_length_cap(self):
        long_name = "a" * 200
        result = sanitize_filename(long_name)
        assert len(result) == 120

    def test_windows_unsafe_chars(self):
        assert sanitize_filename('file<>name*.txt') == 'file_name_.txt'

    def test_multiple_spaces(self):
        assert sanitize_filename('file   name') == 'file name'
