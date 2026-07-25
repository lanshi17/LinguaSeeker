"""Prompt builders for evidence extraction stages."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from ..contracts import ContentBlock, TrackDocument

def map_block_type(block_type: str) -> str:
    if block_type == "table":
        return "table"
    if block_type == "image":
        return "image"
    if block_type == "chart":
        return "figure"
    return "text"


def block_readable_text(block: ContentBlock) -> str:
    parts: list[str] = []
    parts.extend(block.table_caption)
    parts.extend(block.image_caption)
    parts.extend(block.chart_caption)
    for value in (block.text, block.content, block.table_body, block.code_body):
        if value.strip():
            parts.append(value.strip())
    if block.list_items:
        parts.extend(item.strip() for item in block.list_items if item.strip())
    return "\n".join(parts).strip()


def block_context_ref(block: ContentBlock) -> str:
    captions = block.table_caption or block.image_caption or block.chart_caption
    return captions[0] if captions else ""


def format_block_prompt_entry(index: int, block: ContentBlock, body: str | None = None) -> str:
    block_body = body if body is not None else block_readable_text(block)
    mapped_type = map_block_type(block.type)
    caption = block_context_ref(block)
    caption_part = f" | caption: {caption}" if caption else ""
    return f"[Block {index} | {mapped_type} | page {block.page_idx + 1}{caption_part}]\n{block_body}"


def build_block_prompt_text(
    document: TrackDocument,
    block_indices: Sequence[int] | None = None,
) -> str:
    if not document.blocks:
        return document.formatted_text
    indices = block_indices if block_indices is not None else range(len(document.blocks))
    parts: list[str] = []
    for index in indices:
        if index < 0 or index >= len(document.blocks):
            continue
        block = document.blocks[index]
        body = block_readable_text(block)
        if not body:
            continue
        parts.append(format_block_prompt_entry(index, block, body))
    return "\n\n".join(parts)


