"""Unit tests for MinerU content_list.json parsing logic."""
from __future__ import annotations

from src.core.ingest_and_digitize_data.parse_document.common.converters import (
    block_to_markdown,
    html_table_to_markdown,
    html_table_to_structured,
)
from tests.core.ingest_and_digitize_data.parse_document.test_e2e_mineru import (
    _parse_content_list,
)


class TestHtmlTableToMarkdown:
    """Tests for html_table_to_markdown helper."""

    def test_simple_table(self):
        html = "<table><tr><td>A</td><td>B</td></tr><tr><td>1</td><td>2</td></tr></table>"
        result = html_table_to_markdown(html)
        assert "| A | B |" in result
        assert "| --- | --- |" in result
        assert "| 1 | 2 |" in result

    def test_empty_table(self):
        assert html_table_to_markdown("") == ""
        assert html_table_to_markdown("<table></table>") == ""

    def test_table_with_th_headers(self):
        html = "<table><tr><th>Name</th><th>Value</th></tr><tr><td>X</td><td>42</td></tr></table>"
        result = html_table_to_markdown(html)
        assert "| Name | Value |" in result
        assert "| X | 42 |" in result

    def test_uneven_rows_padded(self):
        html = "<table><tr><td>A</td><td>B</td><td>C</td></tr><tr><td>1</td><td>2</td></tr></table>"
        result = html_table_to_markdown(html)
        # Second row should be padded
        assert "| 1 | 2 |  |" in result


class TestHtmlTableToStructured:
    """Tests for html_table_to_structured helper."""

    def test_extracts_headers_and_rows(self):
        html = "<table><tr><td>A</td><td>B</td></tr><tr><td>1</td><td>2</td></tr></table>"
        headers, rows = html_table_to_structured(html)
        assert headers == ["A", "B"]
        assert rows == [["1", "2"]]

    def test_empty_table(self):
        headers, rows = html_table_to_structured("")
        assert headers == []
        assert rows == []

    def test_single_row_table(self):
        html = "<table><tr><td>Only</td></tr></table>"
        headers, rows = html_table_to_structured(html)
        assert headers == ["Only"]
        assert rows == []


class TestBlockToMarkdown:
    """Tests for block_to_markdown helper."""

    def test_text_block(self):
        assert block_to_markdown({"type": "text", "text": "Hello"}) == "Hello"

    def test_text_block_with_heading(self):
        assert block_to_markdown({"type": "text", "text": "Title", "text_level": 2}) == "## Title"

    def test_image_block_with_footnote(self):
        block = {
            "type": "image",
            "img_path": "images/fig.jpg",
            "image_caption": ["Fig 1"],
            "image_footnote": ["Source: data"],
        }
        result = block_to_markdown(block)
        assert "![Fig 1](images/fig.jpg)" in result
        assert "*Source: data*" in result

    def test_discarded_block_returns_empty(self):
        assert block_to_markdown({"type": "discarded", "text": "noise"}) == ""


class TestContentListParsing:
    """Tests for _parse_content_list."""

    def test_text_blocks_grouped_by_page(self):
        content_list = [
            {"type": "text", "text": "Hello", "page_idx": 0},
            {"type": "text", "text": "World", "page_idx": 0},
            {"type": "text", "text": "Page 2 text", "page_idx": 1},
        ]
        result = _parse_content_list(content_list, "")
        assert result.metadata.total_pages == 2
        assert "Hello" in result.pages[0].markdown
        assert "World" in result.pages[0].markdown
        assert "Page 2 text" in result.pages[1].markdown

    def test_image_block_produces_markdown_image(self):
        content_list = [
            {
                "type": "image",
                "img_path": "images/abc.jpg",
                "image_caption": ["Figure 1: A diagram"],
                "image_footnote": [],
                "bbox": [100, 200, 300, 400],
                "page_idx": 0,
            }
        ]
        result = _parse_content_list(content_list, "")
        assert "![Figure 1: A diagram](images/abc.jpg)" in result.pages[0].markdown

    def test_image_block_without_caption(self):
        content_list = [
            {
                "type": "image",
                "img_path": "images/fig.jpg",
                "image_caption": [],
                "image_footnote": [],
                "bbox": [0, 0, 0, 0],
                "page_idx": 0,
            }
        ]
        result = _parse_content_list(content_list, "")
        assert "![](images/fig.jpg)" in result.pages[0].markdown

    def test_image_block_with_footnote(self):
        content_list = [
            {
                "type": "image",
                "img_path": "images/fig.jpg",
                "image_caption": ["Figure 1"],
                "image_footnote": ["Source: lab data"],
                "bbox": [0, 0, 0, 0],
                "page_idx": 0,
            }
        ]
        result = _parse_content_list(content_list, "")
        md = result.pages[0].markdown
        assert "![Figure 1](images/fig.jpg)" in md
        assert "*Source: lab data*" in md

    def test_table_block_produces_markdown_table(self):
        content_list = [
            {
                "type": "table",
                "img_path": "images/table.jpg",
                "table_caption": ["Table 1: Results"],
                "table_footnote": ["Note: values in mg/dl"],
                "table_body": "<table><tr><td>A</td><td>B</td></tr><tr><td>1</td><td>2</td></tr></table>",
                "bbox": [100, 200, 300, 400],
                "page_idx": 0,
            }
        ]
        result = _parse_content_list(content_list, "")
        page_md = result.pages[0].markdown
        assert "**Table 1: Results**" in page_md
        assert "| A | B |" in page_md
        assert "| 1 | 2 |" in page_md
        assert "*Note: values in mg/dl*" in page_md

    def test_table_block_populates_structured_data(self):
        """Verify TableStructure has real headers/rows, not empty lists."""
        content_list = [
            {
                "type": "table",
                "img_path": "images/table.jpg",
                "table_caption": ["Table 1"],
                "table_footnote": [],
                "table_body": "<table><tr><td>A</td><td>B</td></tr><tr><td>1</td><td>2</td></tr></table>",
                "bbox": [0, 0, 0, 0],
                "page_idx": 0,
            }
        ]
        result = _parse_content_list(content_list, "")
        assert len(result.pages[0].tables) == 1
        table = result.pages[0].tables[0]
        assert table.headers == ["A", "B"]
        assert table.rows == [["1", "2"]]

    def test_discarded_blocks_skipped(self):
        content_list = [
            {"type": "text", "text": "Keep", "page_idx": 0},
            {"type": "discarded", "text": "Skip", "page_idx": 0},
        ]
        result = _parse_content_list(content_list, "")
        assert "Keep" in result.pages[0].markdown
        assert "Skip" not in result.pages[0].markdown

    def test_mixed_content_preserves_order(self):
        content_list = [
            {"type": "text", "text": "Intro", "page_idx": 0},
            {
                "type": "image",
                "img_path": "images/fig.jpg",
                "image_caption": ["Fig 1"],
                "image_footnote": [],
                "bbox": [0, 0, 0, 0],
                "page_idx": 0,
            },
            {"type": "text", "text": "Outro", "page_idx": 0},
        ]
        result = _parse_content_list(content_list, "")
        md = result.pages[0].markdown
        intro_pos = md.index("Intro")
        fig_pos = md.index("![Fig 1]")
        outro_pos = md.index("Outro")
        assert intro_pos < fig_pos < outro_pos

    def test_text_heading_levels(self):
        content_list = [
            {"type": "text", "text": "Title", "text_level": 1, "page_idx": 0},
            {"type": "text", "text": "Subtitle", "text_level": 2, "page_idx": 0},
            {"type": "text", "text": "Body", "page_idx": 0},
        ]
        result = _parse_content_list(content_list, "")
        md = result.pages[0].markdown
        assert "# Title" in md
        assert "## Subtitle" in md
        assert "Body" in md

    def test_empty_content_list_fallback_to_full_markdown(self):
        result = _parse_content_list([], "Fallback content")
        assert result.metadata.total_pages == 1
        assert result.pages[0].markdown == "Fallback content"
