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
