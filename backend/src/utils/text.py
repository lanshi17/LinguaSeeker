"""Text processing utilities."""
from __future__ import annotations

import re


def sanitize_filename(name: str) -> str:
    """Sanitize filename by removing invalid characters.

    Removes Windows-unsafe characters and caps length at 120 chars.
    Returns "paper" if result is empty.

    Args:
        name: Raw filename to sanitize.

    Returns:
        Sanitized filename safe for all platforms.
    """
    cleaned = re.sub(r'[\\/:*?"<>|]+', "_", str(name or "").strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return (cleaned or "paper")[:120]


def strip_json_fences(content: str) -> str:
    """Strip Markdown code fences from LLM JSON output.

    LLMs often wrap JSON responses in ```json ... ``` blocks.
    This function removes those fences while preserving the JSON content.

    Args:
        content: Raw LLM output potentially containing code fences.

    Returns:
        Cleaned JSON string without fences.
    """
    if not content:
        return ""
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return text
