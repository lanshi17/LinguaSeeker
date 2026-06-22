"""Shared markdown parsing helpers used by local and remote document parsers."""
from __future__ import annotations

import re

_ABSTRACT_PATTERN = re.compile(
    r"(?:^|\n)\s*(?:#{1,3}\s*)?(?:\*\*)?(?:Abstract|ABSTRACT|摘要|【摘要】)"
    r"(?:\*\*)?\s*(?::\s*)?\n(.*?)"
    r"(?=\n\s*(?:#{1,3}\s*)?(?:\*\*)?"
    r"(?:Introduction|INTRODUCTION|引言|关键词|Keywords|KEYWORDS|Background|BACKGROUND|1\s*[\.\)])|\Z)",
    re.DOTALL | re.IGNORECASE,
)
_TRAILING_ARTIFACT_RE = re.compile(r"\n\s*[\*\-]\s*$")


def extract_abstract_from_markdown(text: str) -> str | None:
    """Extract abstract text from markdown content.

    Looks for common academic paper patterns:
    - "Abstract" / "ABSTRACT" heading
    - "摘要" / "【摘要】" heading (Chinese)
    Falls back to first substantial paragraph before "Introduction"/"Keywords".
    """
    if not text:
        return None
    m = _ABSTRACT_PATTERN.search(text)
    if m:
        abstract = m.group(1).strip()
        abstract = _TRAILING_ARTIFACT_RE.sub("", abstract).strip()
        if len(abstract) > 30:
            return abstract
    return None
