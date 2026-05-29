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
