"""Text processing utilities — sanitization, JSON cleanup, group-id parsing, abstract extraction."""
from __future__ import annotations

import re

# ── Whitespace ──────────────────────────────────────────────────────────

_MULTI_SPACE_RE = re.compile(r"\s+")
_BRACKET_STRIP_RE = re.compile(r"^\['|^\[\"|'\]$|\"\]$")
_MISSING_GROUP_VALUE = "__missing__"


# ── Filename / JSON ─────────────────────────────────────────────────────


def sanitize_filename(name: str) -> str:
    """Sanitize filename by removing invalid characters.

    Removes Windows-unsafe characters and caps length at 120 chars.
    Returns "paper" if result is empty.
    """
    cleaned = re.sub(r'[\\/:*?"<>|]+', "_", str(name or "").strip())
    cleaned = _MULTI_SPACE_RE.sub(" ", cleaned).strip()
    return (cleaned or "paper")[:120]


def strip_json_fences(content: str) -> str:
    """Strip Markdown code fences from LLM JSON output.

    LLMs often wrap JSON responses in ```json ... ``` blocks.
    This function removes those fences while preserving the JSON content.
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


# ── Group-id parsing ────────────────────────────────────────────────────


def _parse_field_from_group_id(group_id: str, field: str) -> str | None:
    """Extract a field value from a group_id string like 'gene=BRCA1|variant=...'."""
    m = re.search(rf"{field}=([^|]+)", group_id)
    if not m:
        return None
    val = m.group(1).strip()
    if val == _MISSING_GROUP_VALUE or not val:
        return None
    return _BRACKET_STRIP_RE.sub("", val)


def parse_gene_from_group_id(group_id: str) -> str | None:
    """Extract gene from a group_id string like 'gene=BRCA1|variant=...'."""
    return _parse_field_from_group_id(group_id, "gene")


def parse_variant_from_group_id(group_id: str) -> str | None:
    """Extract variant from a group_id string like 'gene=...|variant=...'."""
    return _parse_field_from_group_id(group_id, "variant")


# ── Abstract extraction ─────────────────────────────────────────────────

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
