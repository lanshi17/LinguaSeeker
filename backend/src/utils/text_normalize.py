"""Shared text normalization helpers for the evidence extraction pipeline."""
from __future__ import annotations

import re

SPACE_RE = re.compile(r"\s+")


def normalize_text(value: str) -> str:
    """Collapse whitespace and case-fold a string for comparison."""
    return SPACE_RE.sub(" ", value.strip()).casefold()


def normalize_value(value: str | int | float | bool | list[str] | None) -> str:
    """Normalize a heterogeneous value to a comparable string."""
    if isinstance(value, list):
        return "|".join(sorted(normalize_text(str(item)) for item in value if normalize_text(str(item))))
    if value is None:
        return ""
    return normalize_text(str(value))


def block_text_from_dict(block: dict) -> str:
    """Extract all readable text from a serialized ContentBlock dict.

    Mirrors ``SourceGrounder._block_readable_text`` so that the concatenated
    full text matches the ``formatted_text`` used during extraction — which is
    essential for source-span offsets to remain valid in the evidence viewer.
    """
    parts: list[str] = []
    for caption_key in ("table_caption", "image_caption", "chart_caption", "code_caption"):
        for cap in block.get(caption_key) or []:
            if isinstance(cap, str) and cap.strip():
                parts.append(cap.strip())
    for text_key in ("text", "content", "table_body", "code_body"):
        value = block.get(text_key)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
    for item in block.get("list_items") or []:
        if isinstance(item, str) and item.strip():
            parts.append(item.strip())
    return "\n".join(parts)


def concat_document_text(doc_data: dict) -> str | None:
    """Concatenate text from a persisted JSON document.

    Prefers ``formatted_text`` (the authoritative document text used during
    extraction, so source-span offsets remain valid) when available.
    Falls back to concatenating all text-bearing fields from each block.
    """
    formatted = doc_data.get("formatted_text", "")
    if isinstance(formatted, str) and formatted.strip():
        return formatted.strip()
    blocks = doc_data.get("blocks", [])
    if isinstance(blocks, list) and blocks:
        text = "\n\n".join(
            block_text_from_dict(block)
            for block in blocks
            if isinstance(block, dict) and block_text_from_dict(block)
        )
        if text:
            return text
    return None
