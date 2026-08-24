"""Shared text normalization helpers for the evidence extraction pipeline."""

from __future__ import annotations

import html
import re
from typing import Any

SPACE_RE = re.compile(r"\s+")
_HTML_ENTITY_RE = re.compile(r"&(?:#(?:[xX][0-9a-fA-F]+|\d+)|[a-zA-Z][a-zA-Z0-9]+);")
# MinerU/markdown leftover escapes that appear in HGVS and scientific text.
# Letters after a backslash (`\m`, `\d`) are left alone — they are not markdown.
_MARKDOWN_ESCAPED_PUNCT = frozenset("*_~.-")
_MARKDOWN_ESCAPE_RE = re.compile(r"\\([*_~.\-])")


def unescape_markdown_punctuation(text: str) -> str:
    """Decode markdown punctuation escapes such as ``\\*`` and ``\\~``."""
    return _MARKDOWN_ESCAPE_RE.sub(r"\1", text)


def take_markdown_escape(text: str, index: int) -> tuple[str, int] | None:
    """Return the unescaped punctuation and next index, or None."""
    if index + 1 < len(text) and text[index] == "\\" and text[index + 1] in _MARKDOWN_ESCAPED_PUNCT:
        return text[index + 1], index + 2
    return None


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


def unescape_mined_text(text: str) -> str:
    """Decode HTML entities and markdown punctuation leftover in mined text."""
    if not text:
        return text
    return unescape_markdown_punctuation(html.unescape(text))


def unescape_mined_strings(values: Any) -> list[str]:
    """Decode HTML entities in a list of caption or list-item strings."""
    if not isinstance(values, list):
        return []
    return [unescape_mined_text(str(item)) for item in values]


def html_entity_aliases(text: str) -> tuple[str, ...]:
    """Return HTML-escaped/unescaped forms used by MinerU-style documents."""
    if not text:
        return ()
    aliases: list[str] = []
    unescaped = html.unescape(text)
    if unescaped != text:
        aliases.append(unescaped)
    encoded = html.escape(unescaped, quote=False)
    if encoded not in {text, unescaped}:
        aliases.append(encoded)
    seen = {text, unescaped, *aliases}
    md_decoded = unescape_markdown_punctuation(unescaped)
    if md_decoded not in seen:
        aliases.append(md_decoded)
        seen.add(md_decoded)
    md_encoded = md_decoded.replace("~", "\\~")
    if md_encoded not in seen:
        aliases.append(md_encoded)
        seen.add(md_encoded)
    star_encoded = md_decoded.replace("*", "\\*")
    if star_encoded not in seen:
        aliases.append(star_encoded)
    return tuple(aliases)


def find_html_aware(haystack: str, needle: str, start: int = 0) -> tuple[int, int]:
    """Locate ``needle`` in ``haystack``, treating HTML entities as equivalent.

    Returns ``(start, end)`` offsets into ``haystack``, or ``(-1, -1)``.
    The end offset is the haystack span of the matched form, which may be
    longer than ``needle`` when the document stored ``&gt;`` for ``>``.
    """
    if not needle:
        return (-1, -1)
    start = max(start, 0)
    best: tuple[int, int] | None = None
    seen: set[str] = set()
    for candidate in (needle, *html_entity_aliases(needle)):
        if candidate in seen:
            continue
        seen.add(candidate)
        pos = haystack.find(candidate, start)
        if pos < 0:
            continue
        span = (pos, pos + len(candidate))
        if best is None or pos < best[0] or (pos == best[0] and span[1] < best[1]):
            best = span
    if best is not None:
        return best
    return _find_html_aware_normalized(haystack, needle, start)


def _expand_html_entities(text: str) -> list[tuple[str, int, int]]:
    """Expand named/numeric HTML entities, keeping each char's original span."""
    parts: list[tuple[str, int, int]] = []
    index = 0
    while index < len(text):
        match = _HTML_ENTITY_RE.match(text, index)
        if match is not None:
            raw = match.group(0)
            decoded = html.unescape(raw)
            if decoded != raw:
                end = match.end()
                parts.extend((char, index, end) for char in decoded)
                index = end
                continue
        escaped = take_markdown_escape(text, index)
        if escaped is not None:
            char, next_index = escaped
            parts.append((char, index, next_index))
            index = next_index
            continue
        parts.append((text[index], index, index + 1))
        index += 1
    return parts


def _find_html_aware_normalized(haystack: str, needle: str, start: int) -> tuple[int, int]:
    """Search decoded haystack and project the match back onto original offsets."""
    expanded = _expand_html_entities(haystack)
    if not expanded:
        return (-1, -1)
    decoded = "".join(char for char, _, _ in expanded)
    decoded_needle = unescape_markdown_punctuation(html.unescape(needle))
    decoded_start = 0
    for index, (_, orig_start, _) in enumerate(expanded):
        if orig_start >= start:
            decoded_start = index
            break
    else:
        return (-1, -1)
    pos = decoded.find(decoded_needle, decoded_start)
    end_idx = pos + len(decoded_needle)
    if pos < 0 or end_idx > len(expanded):
        return (-1, -1)
    return (expanded[pos][1], expanded[end_idx - 1][2])


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
                parts.append(unescape_mined_text(cap.strip()))
    for text_key in ("text", "content", "table_body", "code_body"):
        value = block.get(text_key)
        if isinstance(value, str) and value.strip():
            parts.append(unescape_mined_text(value.strip()))
    for item in block.get("list_items") or []:
        if isinstance(item, str) and item.strip():
            parts.append(unescape_mined_text(item.strip()))
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
            block_text_from_dict(block) for block in blocks if isinstance(block, dict) and block_text_from_dict(block)
        )
        if text:
            return text
    return None
