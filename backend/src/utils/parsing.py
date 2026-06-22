"""Shared helpers for parsing group-id strings used across evidence and profile modules."""
from __future__ import annotations

import re

_MISSING_GROUP_VALUE = "__missing__"


def parse_gene_from_group_id(group_id: str) -> str | None:
    """Extract gene from a group_id string like 'gene=BRCA1|variant=...'."""
    m = re.search(r"gene=([^|]+)", group_id)
    if not m:
        return None
    val = m.group(1).strip()
    if val == _MISSING_GROUP_VALUE or not val:
        return None
    val = re.sub(r"^\['|^\[\"|'\]$|\"\]$", "", val)
    return val


def parse_variant_from_group_id(group_id: str) -> str | None:
    """Extract variant from a group_id string like 'gene=...|variant=...'."""
    m = re.search(r"variant=([^|]+)", group_id)
    if not m:
        return None
    val = m.group(1).strip()
    if val == _MISSING_GROUP_VALUE or not val:
        return None
    val = re.sub(r"^\['|^\[\"|'\]$|\"\]$", "", val)
    return val
