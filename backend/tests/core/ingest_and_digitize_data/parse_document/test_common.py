"""Tests for common module."""
from __future__ import annotations



def test_html_table_to_markdown():
    """Test HTML table to markdown conversion."""
    from src.core.ingest_and_digitize_data.parse_document.common.converters import html_table_to_markdown

    html = "<table><tr><th>Name</th><th>Age</th></tr><tr><td>Alice</td><td>30</td></tr></table>"
    result = html_table_to_markdown(html)
    assert "| Name | Age |" in result
    assert "| --- | --- |" in result
    assert "| Alice | 30 |" in result


def test_html_table_to_structured():
    """Test HTML table to structured extraction."""
    from src.core.ingest_and_digitize_data.parse_document.common.converters import html_table_to_structured

    html = "<table><tr><th>Name</th><th>Age</th></tr><tr><td>Alice</td><td>30</td></tr></table>"
    headers, rows = html_table_to_structured(html)
    assert headers == ["Name", "Age"]
    assert rows == [["Alice", "30"]]


def test_block_to_markdown_text():
    """Test text block to markdown conversion."""
    from src.core.ingest_and_digitize_data.parse_document.common.converters import block_to_markdown

    block = {"type": "text", "text": "Hello World", "text_level": 2}
    result = block_to_markdown(block)
    assert result == "## Hello World"


def test_block_to_markdown_image():
    """Test image block to markdown conversion."""
    from src.core.ingest_and_digitize_data.parse_document.common.converters import block_to_markdown

    block = {
        "type": "image",
        "img_path": "test.png",
        "image_caption": ["Test Image"],
        "image_footnote": ["Footnote"],
    }
    result = block_to_markdown(block)
    assert "![Test Image](test.png)" in result
    assert "*Footnote*" in result


def test_block_to_markdown_table():
    """Test table block to markdown conversion."""
    from src.core.ingest_and_digitize_data.parse_document.common.converters import block_to_markdown

    block = {
        "type": "table",
        "table_caption": ["Table 1"],
        "table_body": "<table><tr><th>A</th></tr><tr><td>1</td></tr></table>",
        "table_footnote": ["Note"],
    }
    result = block_to_markdown(block)
    assert "**Table 1**" in result
    assert "| A |" in result
    assert "*Note*" in result
