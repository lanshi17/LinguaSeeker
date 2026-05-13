"""Content conversion utilities."""
from __future__ import annotations

from .parsers import TableParser


def html_table_to_markdown(html: str) -> str:
    """Convert HTML <table> to markdown table format."""
    parser = TableParser()
    parser.feed(html)

    if not parser.rows:
        return ""

    col_count = max(len(row) for row in parser.rows)
    for row in parser.rows:
        while len(row) < col_count:
            row.append("")

    lines = []
    lines.append("| " + " | ".join(parser.rows[0]) + " |")
    lines.append("| " + " | ".join(["---"] * col_count) + " |")
    for row in parser.rows[1:]:
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)


def html_table_to_structured(html: str) -> tuple[list[str], list[list[str]]]:
    """Extract headers and data rows from HTML <table>.

    Returns (headers, rows) where headers is the first row and rows is the rest.
    """
    parser = TableParser()
    parser.feed(html)

    if not parser.rows:
        return [], []

    headers = parser.rows[0]
    rows = parser.rows[1:]
    return headers, rows


def block_to_markdown(block: dict) -> str:
    """Convert a single content_list block to markdown."""
    block_type = block.get("type", "text")

    if block_type == "text":
        text = block.get("text", "")
        level = block.get("text_level")
        if level and isinstance(level, int) and 1 <= level <= 6:
            return f"{'#' * level} {text}"
        return text

    if block_type == "image":
        caption = block.get("image_caption", [])
        img_path = block.get("img_path", "")
        caption_text = caption[0] if caption else ""
        footnote = block.get("image_footnote", [])
        parts = []
        if img_path:
            parts.append(f"![{caption_text}]({img_path})")
        elif caption_text:
            parts.append(caption_text)
        if footnote:
            parts.append(f"*{footnote[0]}*")
        return "\n\n".join(parts)

    if block_type == "table":
        parts = []
        caption = block.get("table_caption", [])
        if caption:
            parts.append(f"**{caption[0]}**")

        table_body = block.get("table_body", "")
        if table_body:
            md_table = html_table_to_markdown(table_body)
            if md_table:
                parts.append(md_table)

        footnote = block.get("table_footnote", [])
        if footnote:
            parts.append(f"*{footnote[0]}*")

        return "\n\n".join(parts)

    return ""
