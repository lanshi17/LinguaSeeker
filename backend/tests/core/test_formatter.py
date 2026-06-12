"""Tests for MarkdownFormatter HTML detection."""

import pytest


def test_apply_llm_formatting_detects_html_response():
    """Formatter must detect HTML in LLM output and skip formatting."""
    from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.format.formatter import _is_html

    html_response = "<html><head><title>404 Not Found</title></head><body><h1>Not Found</h1></body></html>"
    assert _is_html(html_response) is True


def test_is_html_rejects_normal_markdown():
    """Normal markdown should not be detected as HTML."""
    from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.format.formatter import _is_html

    markdown = "# Title\n\nSome **bold** text with [links](http://example.com)."
    assert _is_html(markdown) is False


def test_is_html_detects_doctype():
    """DOCTYPE declarations should be detected as HTML."""
    from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.format.formatter import _is_html

    html = "<!DOCTYPE html><html><body>Content</body></html>"
    assert _is_html(html) is True


def test_is_html_detects_body_tag():
    """Content starting with <body> should be detected as HTML."""
    from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.format.formatter import _is_html

    html = "<body><p>Error page</p></body>"
    assert _is_html(html) is True
